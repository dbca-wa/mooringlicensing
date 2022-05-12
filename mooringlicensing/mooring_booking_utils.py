from datetime import datetime, timedelta, date
import logging
import traceback
from decimal import *
import json
import calendar
import geojson
import requests
import io
from django.conf import settings
from django.core.urlresolvers import reverse, reverse_lazy
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from dateutil.tz.tz import tzoffset
from pytz import timezone as pytimezone
from ledger.payments.models import Invoice,OracleInterface,CashTransaction
from ledger.payments.utils import oracle_parser_on_invoice, update_payments
from ledger.checkout.utils import create_basket_session, create_checkout_session, place_order_submission, get_cookie_basket
#from mooring.models import (MooringArea, Mooringsite, MooringsiteRate, MooringsiteBooking, Booking, BookingInvoice, MooringsiteBookingRange, Rate, MooringAreaBookingRange,MooringAreaStayHistory, MooringsiteRate, MarinaEntryRate, BookingVehicleRego, AdmissionsBooking, AdmissionsOracleCode, AdmissionsRate, AdmissionsLine, ChangePricePeriod, CancelPricePeriod, GlobalSettings, MooringAreaGroup, AdmissionsLocation, ChangeGroup, CancelGroup, BookingPeriod, BookingPeriodOption, AdmissionsBookingInvoice, BookingAnnualAdmission)
#from mooring import models
#from mooring.serialisers import BookingRegoSerializer, MooringsiteRateSerializer, MarinaEntryRateSerializer, RateSerializer, MooringsiteRateReadonlySerializer, AdmissionsRateSerializer
#from mooring.emails import send_booking_invoice,send_booking_confirmation
#from mooring import emails
from oscar.apps.order.models import Order
from ledger.payments.invoice import utils
#from mooring import models
from mooringlicensing.components.proposals.models import Proposal
from mooringlicensing.components.payments_ml.models import ApplicationFee

logger = logging.getLogger('booking_checkout')

def override_lineitems(override_price, override_reason, total_price, oracle_code, override_reason_info=""):
    invoice_line = []
    if oracle_code:
        #if override_reason:
        discount = Decimal(override_price) - Decimal(override_price) - Decimal(override_price)
        invoice_line.append({"ledger_description": '{} - {}'.format(override_reason.text, override_reason_info), "quantity": 1, 'price_incl_tax': discount, 'oracle_code': oracle_code, 'line_status': 1})
    return invoice_line

def nononline_booking_lineitems(oracle_code, request):
    invoice_line = []
    if oracle_code:
        group = MooringAreaGroup.objects.filter(members__in=[request.user])
        value = GlobalSettings.objects.get(mooring_group=group, key=0).value
        if Decimal(value) > 0:
            invoice_line.append({'ledger_description': 'Phone Booking Fee', 'quantity': 1, 'price_incl_tax': Decimal(value), 'oracle_code': oracle_code, 'line_status': 1})
#            invoice_line.append({'ledger_description': 'Phone Booking Fee', 'quantity': 1, 'price_incl_tax': Decimal(value), 'oracle_code': oracle_code})
    return invoice_line

def admission_lineitems(lines):
    invoice_lines = []
    if lines:
        for line in lines:
            if line['guests'] > 0:
                invoice_lines.append({'ledger_description': 'Admissions {} - {} ({} guests)'.format(line['from'], line['to'], line['guests']), "quantity": 1, 'price_incl_tax': line['admissionFee'], "oracle_code": line['oracle_code'], 'line_status': 1})

#            invoice_lines.append({'ledger_description': 'Admissions {} - {} ({} guests)'.format(line['from'], line['to'], line['guests']), "quantity": 1, 'price_incl_tax': line['admissionFee'], "oracle_code": line['oracle_code']})

    return invoice_lines


def calculate_price_booking_cancellation(booking, overide_cancel_fees=False):
    current_date_time = datetime.strptime(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
    nowtime =  datetime.today()
    nowtimec = datetime.strptime(nowtime.strftime('%Y-%m-%d'),'%Y-%m-%d')
    mg = MooringAreaGroup.objects.all()

    booking = MooringsiteBooking.objects.filter(booking=booking)
    cancellation_fees = []
    adjustment_fee = Decimal('0.00')
    #{'additional_fees': 'true', 'description': 'Booking Change Fee','amount': Decimal('0.00')}

    for ob in booking:
         changed = True
         #for bc in booking_changes:
         #    if bc.campsite == ob.campsite and ob.from_dt == bc.from_dt and ob.to_dt == bc.to_dt and ob.booking_period_option == bc.booking_period_option:
         #       changed = False
         from_dt = datetime.strptime(ob.from_dt.strftime('%Y-%m-%d'),'%Y-%m-%d')
         daystillbooking =  (from_dt-nowtimec).days

         cancel_policy = None
         cancel_fee_amount = '0.00'
         #change_price_period = CancelPricePeriod.objects.filter(id=ob.booking_period_option.cancel_group_id).order_by('days')
         cancel_group =  CancelGroup.objects.get(id=ob.booking_period_option.cancel_group_id)
         cancel_price_period = cancel_group.cancel_period.all().order_by('days')
         mooring_group =None
         for i in mg:
            if i.moorings.count() > 0:
                    mooring_group = i.moorings.all()[0].id 


         for cpp in cancel_price_period:
             if daystillbooking < 0:
                  daystillbooking = 0
             if daystillbooking >= cpp.days:
                  cancel_policy =cpp

         if cancel_policy:
             if cancel_policy.calulation_type == 0:
                 # Percentage
                 cancel_fee_amount = float(ob.amount) * (cancel_policy.percentage / 100)
             elif cancel_policy.calulation_type == 1:
                 cancel_fee_amount = cancel_policy.amount
                 # Fixed Pricing
             description = 'Mooring {} ({} - {})'.format(ob.campsite.mooringarea.name,ob.from_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'),ob.to_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'))

             if overide_cancel_fees is True:
                  cancellation_fees.append({'additional_fees': 'true', 'description': 'Refund - '+description,'amount': str(ob.amount - ob.amount - ob.amount), 'mooring_group': mooring_group, 'oracle_code': str(ob.campsite.mooringarea.oracle_code)})
             else:

                  if datetime.strptime(ob.from_dt.astimezone(pytimezone('Australia/Perth')).strftime('%Y-%m-%d %H:%M:%S'),'%Y-%m-%d %H:%M:%S') < current_date_time:
                      #cancellation_fees.append({'additional_fees': 'true', 'description': 'Past Booking - '+description,'amount': Decimal('0.00'), 'mooring_group': mooring_group})
                      cancellation_fees.append({'additional_fees': 'true', 'description': 'Past Booking - '+description,'amount': Decimal('0.00'), 'mooring_group': mooring_group, 'oracle_code': str(ob.campsite.mooringarea.oracle_code)})
                  else:
                      #change_fees['amount'] = str(refund_amount)
                      cancellation_fees.append({'additional_fees': 'true', 'description': 'Cancel Fee - '+description,'amount': cancel_fee_amount, 'mooring_group': mooring_group, 'oracle_code': str(ob.campsite.mooringarea.oracle_code)})
                      cancellation_fees.append({'additional_fees': 'true', 'description': 'Refund - '+description,'amount': str(ob.amount - ob.amount - ob.amount), 'mooring_group': mooring_group, 'oracle_code': str(ob.campsite.mooringarea.oracle_code)})
                      #cancellation_fees.append({'additional_fees': 'true', 'description': 'Cancel Fee - '+description,'amount': cancel_fee_amount, 'mooring_group': mooring_group})
                      #cancellation_fees.append({'additional_fees': 'true', 'description': 'Refund - '+description,'amount': str(ob.amount - ob.amount - ob.amount), 'mooring_group': mooring_group})
         else:

             print ("NO CANCELATION POLICY")

         #else:
         #    adjustment_fee = ob.amount + adjustment_fee
    #change_fees.append({'additional_fees': 'true', 'description': 'Mooring Adjustment Credit' ,'amount': str(adjustment_fee - adjustment_fee - adjustment_fee)})

    return cancellation_fees



def calculate_price_booking_change(old_booking, new_booking,overide_change_fees=False):
    nowtime =  datetime.today()
    nowtimec = datetime.strptime(nowtime.strftime('%Y-%m-%d'),'%Y-%m-%d')

    old_booking_mooring = MooringsiteBooking.objects.filter(booking=old_booking)
    booking_changes = MooringsiteBooking.objects.filter(booking=new_booking)
    change_fees = []
    adjustment_fee = Decimal('0.00')
    mg = MooringAreaGroup.objects.all()
    #{'additional_fees': 'true', 'description': 'Booking Change Fee','amount': Decimal('0.00')}

    for ob in old_booking_mooring:
         changed = True
         for bc in booking_changes:
             if bc.campsite == ob.campsite and ob.from_dt == bc.from_dt and ob.to_dt == bc.to_dt and ob.booking_period_option == bc.booking_period_option:
                changed = False
         from_dt = datetime.strptime(ob.from_dt.strftime('%Y-%m-%d'),'%Y-%m-%d')
         daystillbooking =  (from_dt-nowtimec).days
         refund_policy = None

         for i in mg:
            if i.moorings.count() > 0:
                    mooring_group = i.moorings.all()[0].id


         if changed is True:
             change_fee_amount = '0.00' 
 #            change_price_period = ChangePricePeriod.objects.filter(id=ob.booking_period_option.change_group_id).order_by('-days')
             change_group =  ChangeGroup.objects.get(id=ob.booking_period_option.change_group_id)
             change_price_period = change_group.change_period.all().order_by('days')
             for cpp in change_price_period:
                  if daystillbooking < 0:
                       daystillbooking = 0
#                  if cpp.days >= daystillbooking:
                  if daystillbooking >= cpp.days:
                      refund_policy =cpp
             if refund_policy:
                if refund_policy.calulation_type == 0:
                    # Percentage
                    change_fee_amount = float(ob.amount) * (refund_policy.percentage / 100)
                elif refund_policy.calulation_type == 1: 
                    change_fee_amount = refund_policy.amount
                    # Fixed Pricing

                description = 'Mooring {} ({} - {})'.format(ob.campsite.mooringarea.name,ob.from_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'),ob.to_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'))

                if overide_change_fees is True:
                     change_fees.append({'additional_fees': 'true', 'description': 'Refund - '+description,'amount': str(format(ob.amount - ob.amount - ob.amount, '.2f')), 'oracle_code': str(ob.campsite.mooringarea.oracle_code), 'mooring_group': mooring_group, 'line_status': 3})
                else:
                       #change_fees['amount'] = str(refund_amount)
                     #change_fees.append({'additional_fees': 'true', 'description': 'Change Fee - '+description,'amount': float(change_fee_amount), 'oracle_code': str(ob.campsite.mooringarea.oracle_code), 'mooring_group': mooring_group})
                     #change_fees.append({'additional_fees': 'true', 'description': 'Refund - '+description,'amount': str(ob.amount - ob.amount - ob.amount), 'oracle_code': str(ob.campsite.mooringarea.oracle_code), 'mooring_group': mooring_group})
                     change_fees.append({'additional_fees': 'true', 'description': 'Change Fee - '+description,'amount': str(format(change_fee_amount, '.2f')), 'oracle_code': str(ob.campsite.mooringarea.oracle_code), 'mooring_group': mooring_group, 'line_status': 2})
                     change_fees.append({'additional_fees': 'true', 'description': 'Refund - '+description,'amount': str(format(ob.amount - ob.amount - ob.amount, '.2f')), 'oracle_code': str(ob.campsite.mooringarea.oracle_code), 'mooring_group': mooring_group, 'line_status': 3})
             else:
                 print ("NO REFUND POLICY")
               
         else:
             #description = 'Mooring {} ({} - {})'.format(ob.campsite.mooringarea.name,ob.from_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'),ob.to_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'))
             adjustment_fee = float('0.00')
             adjustment_fee = float(ob.amount) + adjustment_fee
             description = 'Mooring {} ({} - {})'.format(ob.campsite.mooringarea.name,ob.from_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'),ob.to_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'))
#             change_fees.append({'additional_fees': 'true', 'description': 'Adjustment - '+description ,'amount': str(adjustment_fee - adjustment_fee - adjustment_fee), 'oracle_code': str(ob.campsite.mooringarea.oracle_code), 'mooring_group': mooring_group})   
             change_fees.append({'additional_fees': 'true', 'description': 'Adjustment - '+description ,'amount': str(format(adjustment_fee - adjustment_fee - adjustment_fee, '.2f')), 'oracle_code': str(ob.campsite.mooringarea.oracle_code), 'mooring_group': mooring_group, 'line_status': 3})

    return change_fees

def calculate_price_admissions_cancel(adBooking, change_fees, overide_cancel_fees=False):
    ad_lines = AdmissionsLine.objects.filter(admissionsBooking=adBooking)
    for line in ad_lines:
        if line.arrivalDate > date.today() or overide_cancel_fees is True:
            

            description = "Admission ({}) for {} guest(s)".format(datetime.strftime(line.arrivalDate, '%d/%m/%Y'), adBooking.total_admissions)
            oracle_code = AdmissionsOracleCode.objects.filter(mooring_group=line.location.mooring_group)[0]
    
            change_fees.append({'additional_fees': 'true', 'description': 'Refund - ' +  description,'amount': str(line.cost - line.cost - line.cost), 'oracle_code': str(oracle_code.oracle_code), 'mooring_group': line.location.mooring_group.id, 'line_status': 3})
    return change_fees


def calculate_price_admissions_change(adBooking, change_fees):
    ad_lines = AdmissionsLine.objects.filter(admissionsBooking=adBooking)
    for line in ad_lines:
          
        description = "Admission ({}) for {} guest(s)".format(datetime.strftime(line.arrivalDate, '%d/%m/%Y'), adBooking.total_admissions)
        oracle_code = AdmissionsOracleCode.objects.filter(mooring_group=line.location.mooring_group)[0]
        
        # Fees
        change_fees.append({'additional_fees': 'true', 'description': 'Adjustment - ' +  description,'amount': str(line.cost - line.cost - line.cost), 'oracle_code': str(oracle_code.oracle_code), 'mooring_group': line.location.mooring_group.id, 'line_status': 3 })


    return change_fees

def price_or_lineitems(request,booking,campsite_list,lines=True,old_booking=None):
    total_price = Decimal(0)
    booking_mooring = MooringsiteBooking.objects.filter(booking=booking)
    booking_mooring_old = []
    if booking.old_booking:
        booking_mooring_old = MooringsiteBooking.objects.filter(booking=booking.old_booking)

    invoice_lines = []
    if lines:
        for bm in booking_mooring:
            line_status = 1
            amount = bm.amount
            if str(bm.id) in booking.override_lines:
                amount = Decimal(booking.override_lines[str(bm.id)])
            for ob in booking_mooring_old:
                if bm.campsite == ob.campsite and ob.from_dt == bm.from_dt and ob.to_dt == bm.to_dt and ob.booking_period_option == bm.booking_period_option:
                      line_status = 2
            invoice_lines.append({'ledger_description':'Mooring {} ({} - {})'.format(bm.campsite.mooringarea.name,bm.from_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'),bm.to_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p')),"quantity":1,"price_incl_tax":amount,"oracle_code":bm.campsite.mooringarea.oracle_code, 'line_status': line_status})



#            invoice_lines.append({'ledger_description':'Mooring {} ({} - {})'.format(bm.campsite.mooringarea.name,bm.from_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'),bm.to_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p')),"quantity":1,"price_incl_tax":bm.amount,"oracle_code":bm.campsite.mooringarea.oracle_code})
        return invoice_lines
    else:
        return total_price

def price_or_lineitems_extras(request,booking,change_fees,invoice_lines=[]):
    total_price = Decimal(0)
    booking_mooring = MooringsiteBooking.objects.filter(booking=booking)
    for cf in change_fees:
#       invoice_lines.append({'ledger_description':cf['description'],"quantity":1,"price_incl_tax":cf['amount'],"oracle_code":cf['oracle_code']})
       invoice_lines.append({'ledger_description':cf['description'],"quantity":1,"price_incl_tax":cf['amount'],"oracle_code":cf['oracle_code'], 'line_status': cf['line_status']})
    return invoice_lines 

def old_price_or_lineitems(request,booking,campsite_list,lines=True,old_booking=None):
    total_price = Decimal(0)
    rate_list = {}
    invoice_lines = []
    if not lines and not old_booking:
        raise Exception('An old booking is required if lines is set to false')
    # Create line items for customers
    daily_rates = [get_campsite_current_rate(request,c,booking.arrival.strftime('%Y-%m-%d'),booking.departure.strftime('%Y-%m-%d')) for c in campsite_list]
    if not daily_rates:
        raise Exception('There was an error while trying to get the daily rates.')
    for rates in daily_rates:
        for c in rates:
            if c['rate']['campsite'] not in rate_list.keys():
                rate_list[c['rate']['campsite']] = {c['rate']['id']:{'start':c['date'],'end':c['date'],'mooring': c['rate']['mooring'] ,'adult':c['rate']['adult'],'concession':c['rate']['concession'],'child':c['rate']['child'],'infant':c['rate']['infant']}}
            else:
                if c['rate']['id'] not in rate_list[c['rate']['campsite']].keys():
                    rate_list[c['rate']['campsite']] = {c['rate']['id']:{'start':c['date'],'end':c['date'],'mooring': c['rate']['mooring'], 'adult':c['rate']['adult'],'concession':c['rate']['concession'],'child':c['rate']['child'],'infant':c['rate']['infant']}}
                else:
                    rate_list[c['rate']['campsite']][c['rate']['id']]['end'] = c['date']
    # Get Guest Details
    #guests = {}
    #for k,v in booking.details.items():
    #    if 'num_' in k:
    #        guests[k.split('num_')[1]] = v
    ##### Above is for poeple quantity (mooring are not based on people.. based on vessels)

    # guess is used as the quantity items for the check out basket.
    guests = {}
    guests['mooring'] = 1
    for k,v in guests.items():
        if int(v) > 0:
            for c,p in rate_list.items():
                for i,r in p.items():
                    price = Decimal(0)
                    end = datetime.strptime(r['end'],"%Y-%m-%d").date()
                    start = datetime.strptime(r['start'],"%Y-%m-%d").date()
                    num_days = int ((end - start).days) + 1
                    campsite = Mooringsite.objects.get(id=c)
                    if lines:
                        price = str((num_days * Decimal(r[k])))
                        #if not booking.mooringarea.oracle_code:
                        #    raise Exception('The mooringarea selected does not have an Oracle code attached to it.')
                        end_date = end + timedelta(days=1)
#                        invoice_lines.append({'ledger_description':'Mooring fee {} ({} - {})'.format(k,start.strftime('%d-%m-%Y'),end_date.strftime('%d-%m-%Y')),"quantity":v,"price_incl_tax":price,"oracle_code":booking.mooringarea.oracle_code})
                        invoice_lines.append({'ledger_description':'Admission fee on {} ({}) {}'.format(adLine.arrivalDate, group, overnightStay),"quantity":amount,"price_incl_tax":price, "oracle_code":oracle_code, 'line_status': 1})
                    else:
                        price = (num_days * Decimal(r[k])) * v
                        total_price += price
    # Create line items for vehicles
    if lines:
        vehicles = booking.regos.all()
    else:
        vehicles = old_booking.regos.all()
    if vehicles:
        if booking.mooringarea.park.entry_fee_required:
            # Update the booking vehicle regos with the park entry requirement
            vehicles.update(park_entry_fee=True)
            if not booking.mooringarea.park.oracle_code:
                raise Exception('A marine park entry Oracle code has not been set for the park that the mooringarea belongs to.')
        park_entry_rate = get_park_entry_rate(request,booking.arrival.strftime('%Y-%m-%d'))
        vehicle_dict = {
            'vessel' : vehicles.filter(entry_fee=True, type='vessel'),
            #'vehicle': vehicles.filter(entry_fee=True, type='vehicle'),
            'motorbike': vehicles.filter(entry_fee=True, type='motorbike'),
            'concession': vehicles.filter(entry_fee=True, type='concession')
        }

        for k,v in vehicle_dict.items():
            if v.count() > 0:
                if lines:
                    price =  park_entry_rate[k]
                    regos = ', '.join([x[0] for x in v.values_list('rego')])
                    invoice_lines.append({
                        'ledger_description': 'Mooring fee - {}'.format(k),
                        'quantity': v.count(),
                        'price_incl_tax': price,
                        'oracle_code': booking.mooringarea.park.oracle_code
                    })
                else:
                    price =  Decimal(park_entry_rate[k]) * v.count()
                    total_price += price
    if lines:
        return invoice_lines
    else:
        return total_price

def get_admissions_entry_rate(request,start_date, location):
    res = []
    if start_date:
        start_date = datetime.strptime(start_date,"%Y-%m-%d").date()
        group = location.mooring_group
        price_history = AdmissionsRate.objects.filter(mooring_group__in=[group,], period_start__lte = start_date).order_by('-period_start')
        if price_history:
            serializer = AdmissionsRateSerializer(price_history,many=True,context={'request':request})
            res = serializer.data[0]
    return res

def admissions_price_or_lineitems(request, admissionsBooking,lines=True):
    total_price = Decimal(0)
    rate_list = {}
    invoice_lines = []
    line = lines
    daily_rates = []
    # Create line items for customers
    admissionsLines = AdmissionsLine.objects.filter(admissionsBooking=admissionsBooking)
    for adLine in admissionsLines:
        rate = get_admissions_entry_rate(request,adLine.arrivalDate.strftime('%Y-%m-%d'), adLine.location)
        daily_rate = {'date' : adLine.arrivalDate.strftime('%d/%m/%Y'), 'rate' : rate}
        daily_rates.append(daily_rate)
        oracle_codes = AdmissionsOracleCode.objects.filter(mooring_group__in=[adLine.location.mooring_group,])
        if not oracle_codes.count() > 0:
            if request.user.is_staff:
                raise Exception('Admissions Oracle Code missing, please set up in administration tool.')
            else:
                raise Exception('Please alert {} of the following error message:\nAdmissions Oracle Code missing.'.format(adLine['group']))
    if not daily_rates or daily_rates == []:
        raise Exception('There was an error while trying to get the daily rates.')
    family = 0
    adults = admissionsBooking.noOfAdults
    children = admissionsBooking.noOfChildren
    if adults > 1 and children > 1:
        if adults == children:
            if adults % 2 == 0:
                family = adults//2
                adults = 0
                children = 0
            else:
                adults -= 1
                family = adults//2
                adults = 1
                children = 1
        elif adults > children: #Adults greater - tickets based on children
            if children % 2 == 0:
                family = children//2
                adults -= children
                children = 0
            else:
                children -= 1
                family = children//2
                adults -= children
                children = 1
        else: #Children greater - tickets based on adults
            if adults % 2 == 0:
                family = adults//2
                children -= adults
                adults = 0
            else:
                adults -= 1
                family = adults//2
                children -= adults
                adults = 1

    people = {'Adults': adults,'Concessions': admissionsBooking.noOfConcessions,'Children': children,'Infants': admissionsBooking.noOfInfants, 'Family': family}
    for adLine in admissionsLines:
        for group, amount in people.items():
            if line:
                if (amount > 0):
                    if group == 'Adults':
                        gr = 'adult'
                    elif group == 'Children':
                        gr = group
                    elif group == 'Infants':
                        gr = 'infant'
                    elif group == 'Family':
                        gr = 'family'
                    if adLine.overnightStay:
                        costfield = gr.lower() + "_overnight_cost"
                        overnightStay = "Overnight Included"
                    else:
                        costfield = gr.lower() + "_cost"
                        overnightStay = "Day Visit Only"
                    daily_rate = next(item for item in daily_rates if item['date'] == adLine.arrivalDate.strftime('%d/%m/%Y'))['rate']
                    price = daily_rate.get(costfield)
                    oracle_codes = AdmissionsOracleCode.objects.filter(mooring_group=adLine.location.mooring_group)
                    if oracle_codes.count() > 0:
                        oracle_code = oracle_codes[0].oracle_code
                    invoice_lines.append({'ledger_description':'Admission fee on {} ({}) {}'.format(adLine.arrivalDate, group, overnightStay),"quantity":amount,"price_incl_tax":price, "oracle_code":oracle_code, 'line_status': 1})
                
            else:
                daily_rate = daily_rates[adLine.arrivalDate.strftime('%d/%m/%Y')]
                price = Decimal(daily_rate)
                total_cost += price
    if line:
        return invoice_lines
    else:
        return total_price

def check_date_diff(old_booking,new_booking):
    if old_booking.arrival == new_booking.arrival and old_booking.departure == new_booking.departure:
        return 4 # same days
    elif old_booking.arrival == new_booking.arrival:
        old_booking_days = int((old_booking.departure - old_booking.arrival).days)
        new_days = int((new_booking.departure - new_booking.arrival).days)
        if new_days > old_booking_days:
            return 1 #additional days
        else:
            return 2 #reduced days
    elif old_booking.departure == new_booking.departure:
        old_booking_days = int((old_booking.departure - old_booking.arrival).days)
        new_days = int((new_booking.departure - new_booking.arrival).days)
        if new_days > old_booking_days:
            return 1 #additional days
        else:
            return 2 #reduced days
    else:
        return 3 # different days

def get_diff_days(old_booking,new_booking,additional=True):
    if additional:
        return int((new_booking.departure - old_booking.departure).days)
    return int((old_booking.departure - new_booking.departure).days)

def create_temp_bookingupdate(request,arrival,departure,booking_details,old_booking,total_price):
    # delete all the campsites in the old moving so as to transfer them to the new booking
    old_booking.campsites.all().delete()
    booking = create_booking_by_site(booking_details['campsites'],
            start_date = arrival,
            end_date = departure,
            num_adult = booking_details['num_adult'],
            num_concession= booking_details['num_concession'],
            num_child= booking_details['num_child'],
            num_infant= booking_details['num_infant'],
            num_mooring = booking_details['num_mooring'],
            cost_total = total_price,
            customer = old_booking.customer,
            override_price=old_booking.override_price,
            updating_booking = True,
            override_checks=True
    )
    # Move all the vehicles to the new booking
    for r in old_booking.regos.all():
        r.booking = booking
        r.save()
    
    lines = price_or_lineitems(request,booking,booking.campsite_id_list)
    booking_arrival = booking.arrival.strftime('%d-%m-%Y')
    booking_departure = booking.departure.strftime('%d-%m-%Y')
    reservation = u'Reservation for {} confirmation PS{}'.format(
            u'{} {}'.format(booking.customer.first_name, booking.customer.last_name), booking.id)
    # Proceed to generate invoice

    checkout_response = checkout(request,booking,lines,invoice_text=reservation,internal=True)

    # FIXME: replace with session check
    invoice = None
    if 'invoice=' in checkout_response.url:
        invoice = checkout_response.url.split('invoice=', 1)[1]
    else:
        for h in reversed(checkout_response.history):
            if 'invoice=' in h.url:
                invoice = h.url.split('invoice=', 1)[1]
                break
    
    # create the new invoice
    new_invoice = internal_create_booking_invoice(booking, invoice)

    # Check if the booking is a legacy booking and doesn't have an invoice
    if old_booking.legacy_id and old_booking.invoices.count() < 1:
        # Create a cash transaction in order to fix the outstnding invoice payment
        CashTransaction.objects.create(
            invoice = Invoice.objects.get(reference=new_invoice.invoice_reference),
            amount = old_booking.cost_total,
            type = 'move_in',
            source = 'cash',
            details = 'Transfer of funds from migrated booking',
            movement_reference='Migrated Booking Funds'
        )
        # Update payment details for the new invoice
        update_payments(new_invoice.invoice_reference)

    # Attach new invoices to old booking
    for i in old_booking.invoices.all():
        inv = Invoice.objects.get(reference=i.invoice_reference)
        inv.voided = True
        #transfer to the new invoice
        inv.move_funds(inv.transferable_amount,Invoice.objects.get(reference=new_invoice.invoice_reference),'Transfer of funds from {}'.format(inv.reference))
        inv.save()
    # Change the booking for the selected invoice
    new_invoice.booking = old_booking
    new_invoice.save()

    return booking


def get_annual_admissions_pricing_info(annual_booking_period_id,vessel_size):
    nowdt = datetime.now()
    price = '0.00'
    annual_admissions = {'response': 'error', 'abpg': {}, 'abpo': {}, 'abpovc': {}}
    if models.AnnualBookingPeriodGroup.objects.filter(id=int(annual_booking_period_id)).count() > 0:
         abpg = models.AnnualBookingPeriodGroup.objects.get(id=int(annual_booking_period_id))
         vsc = models.VesselSizeCategory.objects.filter(start_size__lte=Decimal(vessel_size),end_size__gte=Decimal(vessel_size))
         abpo= models.AnnualBookingPeriodOption.objects.filter(start_time__lte=nowdt,finish_time__gte=nowdt,annual_booking_period_group=abpg)
         if abpo.count() > 0 and vsc.count() > 0:
             abpovc = models.AnnualBookingPeriodOptionVesselCategoryPrice.objects.filter(annual_booking_period_option=abpo[0],vessel_category=vsc[0])
             price = abpovc[0].price
             annual_admissions['abpg'] = abpg
             if abpo.count() > 0: 
                 annual_admissions['abpo'] = abpo[0]
             if abpovc.count() > 0:
                 annual_admissions['abpovc'] = abpovc[0]
                 annual_admissions['response'] = 'success'
    return annual_admissions


def iiiicreate_temp_bookingupdate(request,arrival,departure,booking_details,old_booking,total_price):
    # delete all the campsites in the old moving so as to transfer them to the new booking
    old_booking.campsites.all().delete()
    booking = create_booking_by_site(booking_details['campsites'][0],
            start_date = arrival,
            end_date = departure,
            num_adult = booking_details['num_adult'],
            num_concession= booking_details['num_concession'],
            num_child= booking_details['num_child'],
            num_infant= booking_details['num_infant'],
            num_mooring = booking_details['num_mooring'],
            cost_total = total_price,
            customer = old_booking.customer,
            updating_booking = True
    )

    # Move all the vehicles to the new booking
    for r in old_booking.regos.all():
        r.booking = booking
        r.save()
    
    lines = price_or_lineitems(request,booking,booking.campsite_id_list)
    booking_arrival = booking.arrival.strftime('%d-%m-%Y')
    booking_departure = booking.departure.strftime('%d-%m-%Y')
    reservation = "Reservation for {} from {} to {} at {}".format('{} {}'.format(booking.customer.first_name,booking.customer.last_name),booking_arrival,booking_departure,booking.mooringarea.name)

    # Proceed to generate invoice
    checkout_response = checkout(request,booking,lines,invoice_text=reservation,internal=True)
    internal_create_booking_invoice(booking, checkout_response)
    
    # Get the new invoice
    new_invoice = booking.invoices.first()

    # Check if the booking is a legacy booking and doesn't have an invoice
    if old_booking.legacy_id and old_booking.invoices.count() < 1:
        # Create a cash transaction in order to fix the outstnding invoice payment
        CashTransaction.objects.create(
            invoice = Invoice.objects.get(reference=new_invoice.invoice_reference),
            amount = old_booking.cost_total,
            type = 'move_in',
            source = 'cash',
            details = 'Transfer of funds from migrated booking',
            movement_reference='Migrated Booking Funds'
        )
        # Update payment details for the new invoice
        update_payments(new_invoice.invoice_reference)

    # Attach new invoices to old booking
    for i in old_booking.invoices.all():
        inv = Invoice.objects.get(reference=i.invoice_reference)
        inv.voided = True
        #transfer to the new invoice
        inv.move_funds(inv.transferable_amount,Invoice.objects.get(reference=new_invoice.invoice_reference),'Transfer of funds from {}'.format(inv.reference))
        inv.save()
    # Change the booking for the selected invoice
    new_invoice.booking = old_booking
    new_invoice.save()
    return booking

def update_booking(request,old_booking,booking_details):
    same_dates = False
    same_campsites = False
    same_campground = False
    same_details = False
    same_vehicles = True

    with transaction.atomic():
        try:
            set_session_booking(request.session, old_booking)
            new_details = {}
            new_details.update(old_booking.details)
            # Update the guests
            new_details['num_adult'] =  booking_details['num_adult']
            new_details['num_concession'] = booking_details['num_concession']
            new_details['num_child'] = booking_details['num_child']
            new_details['num_infant'] = booking_details['num_infant']
            booking = Booking(
                arrival = booking_details['start_date'],
                departure =booking_details['end_date'],
                details = new_details,
                customer=old_booking.customer,
                mooringarea = MooringArea.objects.get(id=booking_details['mooringarea']))
            # Check that the departure is not less than the arrival
            if booking.departure < booking.arrival:
                raise Exception('The departure date cannot be before the arrival date')
            today = datetime.now().date()
            if today > old_booking.departure:
                raise ValidationError('You cannot change a booking past the departure date.')
            # Check if it is the same campground
            if old_booking.mooringarea.id == booking.mooringarea.id:
                same_campground = True
            # Check if dates are the same
            if (old_booking.arrival == booking.arrival) and (old_booking.departure == booking.departure):
                same_dates = True
            # Check if the campsite is the same
            if sorted(old_booking.campsite_id_list) == sorted(booking_details['campsites']):
                same_campsites = True
            # Check if the details have changed
            if new_details == old_booking.details:
                same_details = True
            # Check if the vehicles have changed
            current_regos = old_booking.regos.all()
            current_vehicle_regos= sorted([r.rego for r in current_regos])

            # Add history
            new_history = old_booking._generate_history(user=request.user)
            
            if request.data.get('entryFees').get('regos'):
                new_regos = request.data['entryFees'].pop('regos')
                sent_regos = [r['rego'] for r in new_regos]
                regos_serializers = []
                update_regos_serializers = []
                for n in new_regos:
                    if n['rego'] not in current_vehicle_regos:
                        n['booking'] = old_booking.id
                        regos_serializers.append(BookingRegoSerializer(data=n))
                        same_vehicles = False
                    else:
                        booking_rego = BookingVehicleRego.objects.get(booking=old_booking,rego=n['rego'])
                        n['booking'] = old_booking.id
                        if booking_rego.type != n['type'] or booking_rego.entry_fee != n['entry_fee']:
                            update_regos_serializers.append(BookingRegoSerializer(booking_rego,data=n))
                # Create the new regos if they are there
                if regos_serializers:
                    for r in regos_serializers:
                        r.is_valid(raise_exception=True)
                        r.save()
                # Update the new regos if they are there
                if update_regos_serializers:
                    for r in update_regos_serializers:
                        r.is_valid(raise_exception=True)
                        r.save()
                    same_vehicles = False

                # Check if there are regos in place that need to be removed
                stale_regos = []
                for r in current_regos:
                    if r.rego not in sent_regos:
                        stale_regos.append(r.id)
                # delete stale regos
                if stale_regos:
                    same_vehicles = False
                    BookingVehicleRego.objects.filter(id__in=stale_regos).delete()
            else:
                same_vehicles = False
                if current_regos:
                    current_regos.delete()

            if same_campsites and same_dates and same_vehicles and same_details:
                if new_history is not None:
                   new_history.delete()
                return old_booking

            # Check difference of dates in booking
            old_booking_days = int((old_booking.departure - old_booking.arrival).days)
            new_days = int((booking_details['end_date'] - booking_details['start_date']).days)
            date_diff = check_date_diff(old_booking,booking)

            total_price = price_or_lineitems(request,booking,booking_details['campsites'],lines=False,old_booking=old_booking)
            price_diff = True
            if old_booking.cost_total != total_price:
                price_diff = True
            if price_diff:

                booking = create_temp_bookingupdate(request,booking.arrival,booking.departure,booking_details,old_booking,total_price)
                # Attach campsite booking objects to old booking
                for c in booking.campsites.all():
                    c.booking = old_booking
                    c.save()
                # Move all the vehicles to the in new booking to the old booking
                for r in booking.regos.all():
                    r.booking = old_booking
                    r.save()
                old_booking.cost_total = booking.cost_total
                old_booking.departure = booking.departure
                old_booking.arrival = booking.arrival
                old_booking.details.update(booking.details)
                if not same_campground:
                    old_booking.campground = booking.campground
                old_booking.save()
                booking.delete()
            delete_session_booking(request.session)
            send_booking_invoice(old_booking)
            # send out the confirmation email if the booking is paid or over paid
            if old_booking.status == 'Paid' or old_booking.status == 'Over Paid':
                send_booking_confirmation(old_booking,request)
            return old_booking
        except:
            delete_session_booking(request.session)
            print(traceback.print_exc())
            raise

def create_or_update_booking(request,booking_details,updating=False,override_checks=False):
    booking = None
    if not updating:
        booking = create_booking_by_site(booking_details['campsites'],
            start_date = booking_details['start_date'],
            end_date=booking_details['end_date'],
            num_adult=booking_details['num_adult'],
            num_concession=booking_details['num_concession'],
            num_child=booking_details['num_child'],
            num_infant=booking_details['num_infant'],
            num_mooring=booking_details['num_mooring'],
            vessel_size=booking_details['vessel_size'],
            cost_total=booking_details['cost_total'],
            override_price=booking_details['override_price'],
            override_reason=booking_details['override_reason'],
            override_reason_info=booking_details['override_reason_info'],
            overridden_by=booking_details['overridden_by'],
            customer=booking_details['customer'],
            override_checks=override_checks
        )
        
        booking.details['first_name'] = booking_details['first_name']
        booking.details['last_name'] = booking_details['last_name']
        booking.details['phone'] = booking_details['phone']
        booking.details['country'] = booking_details['country']
        booking.details['postcode'] = booking_details['postcode']

        # Add booking regos
        if 'regos' in booking_details:
            regos = booking_details['regos']
            for r in regos:
                r['booking'] = booking.id
            regos_serializers = [BookingRegoSerializer(data=r) for r in regos]
            for r in regos_serializers:
                r.is_valid(raise_exception=True)
                r.save()
        booking.save()
    return booking

def old_create_or_update_booking(request,booking_details,updating=False):
    booking = None
    if not updating:
        booking = create_booking_by_site(campsite_id= booking_details['campsite_id'],
            start_date = booking_details['start_date'],
            end_date=booking_details['end_date'],
            num_adult=booking_details['num_adult'],
            num_concession=booking_details['num_concession'],
            num_child=booking_details['num_child'],
            num_infant=booking_details['num_infant'],
            num_mooring=booking_details['num_mooring'],
            vessel_size=booking_details['vessel_size'],
            cost_total=booking_details['cost_total'],
            customer=booking_details['customer'])
        
        booking.details['first_name'] = booking_details['first_name']
        booking.details['last_name'] = booking_details['last_name']
        booking.details['phone'] = booking_details['phone']
        booking.details['country'] = booking_details['country']
        booking.details['postcode'] = booking_details['postcode']

        # Add booking regos
        if request.data.get('parkEntry').get('regos'):
            regos = request.data['parkEntry'].pop('regos')
            for r in regos:
                r[u'booking'] = booking.id
            regos_serializers = [BookingRegoSerializer(data=r) for r in regos]
            for r in regos_serializers:
                r.is_valid(raise_exception=True)
                r.save()
        booking.save()
    return booking

def admissionsCheckout(request, admissionsBooking, lines, invoice_text=None, vouchers=[], internal=False):
    basket_params = {
        'products': lines,
        'vouchers': vouchers,
        'system': settings.PS_PAYMENT_SYSTEM_ID,
        'custom_basket': True,
        'booking_reference': 'AD-'+str(admissionsBooking.id)
    }
    
    basket, basket_hash = create_basket_session(request, basket_params)
    checkout_params = {
        'system': settings.PS_PAYMENT_SYSTEM_ID,
        'fallback_url': request.build_absolute_uri('/'),
        'return_url': request.build_absolute_uri(reverse('public_admissions_success')),
        'return_preload_url': request.build_absolute_uri(reverse('public_admissions_success')),
        'force_redirect': True,
        'proxy': True if internal else False,
        'invoice_text': invoice_text,
    }
    
    if internal or request.user.is_anonymous():
        checkout_params['basket_owner'] = admissionsBooking.customer.id
    create_checkout_session(request, checkout_params)

    if internal:
        responseJson = place_order_submission(request)
    else:
        print(reverse('checkout:index'))
        responseJson = HttpResponse(geojson.dumps({'status': 'success','redirect': reverse('checkout:index'),}), content_type='application/json')
        # response = HttpResponseRedirect(reverse('checkout:index'))

        # inject the current basket into the redirect response cookies
        # or else, anonymous users will be directionless
        responseJson.set_cookie(
            settings.OSCAR_BASKET_COOKIE_OPEN, basket_hash,
            max_age=settings.OSCAR_BASKET_COOKIE_LIFETIME,
            secure=settings.OSCAR_BASKET_COOKIE_SECURE, httponly=True
        )
    return responseJson

def get_basket(request):
    return get_cookie_basket(settings.OSCAR_BASKET_COOKIE_OPEN,request)

def annual_admission_checkout(request, booking, lines, invoice_text=None, vouchers=[], internal=False):

    basket_params = {
        'products': lines,
        'vouchers': vouchers,
        'system': settings.PS_PAYMENT_SYSTEM_ID,
        'custom_basket': True,
        'booking_reference': 'AA-'+str(booking.id)
    }
    basket, basket_hash = create_basket_session(request, basket_params)
    checkout_params = {
        'system': settings.PS_PAYMENT_SYSTEM_ID,
        'fallback_url': request.build_absolute_uri('/'),
        'return_url': request.build_absolute_uri(reverse('public_booking_annual_admission_success')),
        'return_preload_url': request.build_absolute_uri(reverse('public_booking_annual_admission_success')),
        'force_redirect': True,
        'proxy': True if internal else False,
        'invoice_text': invoice_text,
    }
    if internal or request.user.is_anonymous():
        checkout_params['basket_owner'] = booking.customer.id

    create_checkout_session(request, checkout_params)



#    if internal:
#        response = place_order_submission(request)
#    else:
    response = HttpResponseRedirect(reverse('checkout:index'))
    # inject the current basket into the redirect response cookies
    # or else, anonymous users will be directionless
    response.set_cookie(
            settings.OSCAR_BASKET_COOKIE_OPEN, basket_hash,
            max_age=settings.OSCAR_BASKET_COOKIE_LIFETIME,
            secure=settings.OSCAR_BASKET_COOKIE_SECURE, httponly=True
    )

    #if booking.cost_total < 0:
    #    response = HttpResponseRedirect('/refund-payment')
    #    response.set_cookie(
    #        settings.OSCAR_BASKET_COOKIE_OPEN, basket_hash,
    #        max_age=settings.OSCAR_BASKET_COOKIE_LIFETIME,
    #        secure=settings.OSCAR_BASKET_COOKIE_SECURE, httponly=True
    #    )

    ## Zero booking costs
    #if booking.cost_total < 1 and booking.cost_total > -1:
    #    response = HttpResponseRedirect('/no-payment')
    #    response.set_cookie(
    #        settings.OSCAR_BASKET_COOKIE_OPEN, basket_hash,
    #        max_age=settings.OSCAR_BASKET_COOKIE_LIFETIME,
    #        secure=settings.OSCAR_BASKET_COOKIE_SECURE, httponly=True
    #    )
    return response


def checkout(request, booking, lines, invoice_text=None, vouchers=[], internal=False):
    basket_params = {
        'products': lines,
        'vouchers': vouchers,
        'system': settings.PS_PAYMENT_SYSTEM_ID,
        'custom_basket': True,
        'booking_reference': 'PS-'+str(booking.id)
    }
 
    basket, basket_hash = create_basket_session(request, basket_params)
    checkout_params = {
        'system': settings.PS_PAYMENT_SYSTEM_ID,
        'fallback_url': request.build_absolute_uri('/'),
        'return_url': request.build_absolute_uri(reverse('public_booking_success')),
        'return_preload_url': request.build_absolute_uri(reverse('public_booking_success')),
        'force_redirect': True,
        'proxy': True if internal else False,
        'invoice_text': invoice_text,
    }
#    if not internal:
#        checkout_params['check_url'] = request.build_absolute_uri('/api/booking/{}/booking_checkout_status.json'.format(booking.id))
    if internal or request.user.is_anonymous():
        checkout_params['basket_owner'] = booking.customer.id

    print ("BOOKING ID 3")
    print (request.session['ps_booking'])

    create_checkout_session(request, checkout_params)
    print ("BOOKING ID 4")
    print (request.session['ps_booking'])



#    if internal:
#        response = place_order_submission(request)
#    else:
    #response = HttpResponseRedirect(reverse('checkout:index'))
    response = HttpResponse("<script> window.location='"+reverse('checkout:index')+"';</script> <a href='"+reverse('checkout:index')+"'> Redirecting please wait: "+reverse('checkout:index')+"</a>")

    # inject the current basket into the redirect response cookies
    # or else, anonymous users will be directionless
    response.set_cookie(
            settings.OSCAR_BASKET_COOKIE_OPEN, basket_hash,
            max_age=settings.OSCAR_BASKET_COOKIE_LIFETIME,
            secure=settings.OSCAR_BASKET_COOKIE_SECURE, httponly=True
    )

    if booking.cost_total < 0:
        response = HttpResponseRedirect('/refund-payment')
        response.set_cookie(
            settings.OSCAR_BASKET_COOKIE_OPEN, basket_hash,
            max_age=settings.OSCAR_BASKET_COOKIE_LIFETIME,
            secure=settings.OSCAR_BASKET_COOKIE_SECURE, httponly=True
        )

    # Zero booking costs
    if booking.cost_total < 1 and booking.cost_total > -1:
        response = HttpResponseRedirect('/no-payment')
        response.set_cookie(
            settings.OSCAR_BASKET_COOKIE_OPEN, basket_hash,
            max_age=settings.OSCAR_BASKET_COOKIE_LIFETIME,
            secure=settings.OSCAR_BASKET_COOKIE_SECURE, httponly=True
        )
    return response


def allocate_failedrefund_to_unallocated(request, booking, lines, invoice_text=None, internal=False, order_total='0.00',user=None):
        booking_reference = None
        if booking.__class__.__name__ == 'AdmissionsBooking':
             booking_reference = 'AD-'+str(booking.id)
        elif booking.__class__.__name__ == 'BookingAnnualAdmission':
             booking_reference = 'AA-'+str(booking.id)
        else:
             booking_reference = 'PS-'+str(booking.id)

        basket_params = {
            'products': lines,
            'vouchers': [],
            'system': settings.PS_PAYMENT_SYSTEM_ID,
            'custom_basket': True,
            'booking_reference': booking_reference
        }

        basket, basket_hash = create_basket_session(request, basket_params)
        ci = utils.CreateInvoiceBasket()
        order  = ci.create_invoice_and_order(basket, total=None, shipping_method='No shipping required',shipping_charge=False, user=user, status='Submitted', invoice_text='Refund Allocation Pool', )
        #basket.status = 'Submitted'
        #basket.save()
        #new_order = Order.objects.get(basket=basket)
        new_invoice = Invoice.objects.get(order_number=order.number)
        update_payments(new_invoice.reference)
        if booking.__class__.__name__ == 'AdmissionsBooking':
            print ("AdmissionsBooking")
            book_inv, created = AdmissionsBookingInvoice.objects.get_or_create(admissions_booking=booking, invoice_reference=new_invoice.reference, system_invoice=True)
        elif booking.__class__.__name__ == 'BookingAnnualAdmission':
            print ("BookingAnnualAdmission")
            book_inv, created = models.BookingAnnualInvoice.objects.get_or_create(booking_annual_admission=booking, invoice_reference=new_invoice.reference, system_invoice=True)
        else:
            book_inv, created = BookingInvoice.objects.get_or_create(booking=booking, invoice_reference=new_invoice.reference, system_invoice=True)

        return order

# Booking changed to Proposal
def allocate_refund_to_invoice(request, booking, lines, invoice_text=None, internal=False, order_total='0.00',user=None):
        booking_reference = None
        #if booking.__class__.__name__ == 'AdmissionsBooking':
        #     booking_reference = 'AD-'+str(booking.id)
        #elif booking.__class__.__name__ == 'BookingAnnualAdmission':
        #     booking_reference = 'AA-'+str(booking.id)
        #else:
            #booking_reference = 'PS-'+str(booking.id)
        booking_reference = booking.lodgement_number

        basket_params = {
            'products': lines,
            'vouchers': [],
            'system': settings.PS_PAYMENT_SYSTEM_ID,
            'custom_basket': True,
            'booking_reference': booking_reference
        }

        basket, basket_hash = create_basket_session(request, basket_params)
        ci = utils.CreateInvoiceBasket()
        order  = ci.create_invoice_and_order(basket, total=None, shipping_method='No shipping required',shipping_charge=False, user=user, status='Submitted', invoice_text='Oracle Allocation Pools', )
        #basket.status = 'Submitted'
        #basket.save()
        #new_order = Order.objects.get(basket=basket)
        new_invoice = Invoice.objects.get(order_number=order.number)
        update_payments(new_invoice.reference)
        #if booking.__class__.__name__ == 'AdmissionsBooking':
        #    print ("AdmissionsBooking")
        #    book_inv, created = AdmissionsBookingInvoice.objects.get_or_create(admissions_booking=booking, invoice_reference=new_invoice.reference, system_invoice=True)
        #elif booking.__class__.__name__ == 'BookingAnnualAdmission':
        #    print ("BookingAnnualAdmission")
        #    book_inv, created = models.BookingAnnualInvoice.objects.get_or_create(booking_annual_admission=booking, invoice_reference=new_invoice.reference, system_invoice=True)
        #else:
            
        book_inv, created = ApplicationFee.objects.get_or_create(proposal=booking, invoice_reference=new_invoice.reference, system_invoice=True)

        return order

def old_internal_create_booking_invoice(booking, checkout_response):
    if not checkout_response.history:
        raise Exception('There was a problem retrieving the invoice for this booking')
    last_redirect = checkout_response.history[-2]
    reference = last_redirect.url.split('=')[1]
    try:
        Invoice.objects.get(reference=reference)
    except Invoice.DoesNotExist:
        raise Exception("There was a problem attaching an invoice for this booking")
    book_inv = BookingInvoice.objects.get_or_create(booking=booking,invoice_reference=reference)
    return book_inv

def internal_create_booking_invoice(booking, reference):
    try:
        Invoice.objects.get(reference=reference)
    except Invoice.DoesNotExist:
        raise Exception("There was a problem attaching an invoice for this booking")
    book_inv = BookingInvoice.objects.get_or_create(booking=booking,invoice_reference=reference)
    return book_inv



def internal_booking(request,booking_details,internal=True,updating=False):
    json_booking = request.data
    booking = None
    try:
        booking = create_or_update_booking(request, booking_details, updating, override_checks=internal)
        with transaction.atomic():
            set_session_booking(request.session,booking)
            # Get line items
            booking_arrival = booking.arrival.strftime('%d-%m-%Y')
            booking_departure = booking.departure.strftime('%d-%m-%Y')
            reservation = u"Reservation for {} confirmation PS{}".format(u'{} {}'.format(booking.customer.first_name,booking.customer.last_name), booking.id)
            lines = price_or_lineitems(request,booking,booking.campsite_id_list)

            # Proceed to generate invoice
            checkout_response = checkout(request,booking,lines,invoice_text=reservation,internal=True)
            # Change the type of booking
            booking.booking_type = 0
            booking.save()

            # FIXME: replace with session check
            invoice = None
            if 'invoice=' in checkout_response.url:
                invoice = checkout_response.url.split('invoice=', 1)[1]
            else:
                for h in reversed(checkout_response.history):
                    if 'invoice=' in h.url:
                        invoice = h.url.split('invoice=', 1)[1]
                        break
            print ("-== internal_booking ==-")
            internal_create_booking_invoice(booking, invoice)
            delete_session_booking(request.session)
            send_booking_invoice(booking)
            return booking

    except:
        if booking: 
            booking.delete()
        raise


def old_internal_booking(request,booking_details,internal=True,updating=False):
    json_booking = request.data
    booking = None
    try:
        booking = create_or_update_booking(request,booking_details,updating)
        with transaction.atomic():
            set_session_booking(request.session,booking)
            # Get line items
            booking_arrival = booking.arrival.strftime('%d-%m-%Y')
            booking_departure = booking.departure.strftime('%d-%m-%Y')
            reservation = u"Reservation for {} from {} to {} at {}".format(u'{} {}'.format(booking.customer.first_name,booking.customer.last_name),booking_arrival,booking_departure,booking.mooringarea.name)
            lines = price_or_lineitems(request,booking,booking.campsite_id_list)

            # Proceed to generate invoice
            checkout_response = checkout(request,booking,lines,invoice_text=reservation,internal=True)
            # Change the type of booking
            booking.booking_type = 0
            booking.save()
            internal_create_booking_invoice(booking, checkout_response)
            delete_session_booking(request.session)
            send_booking_invoice(booking)
            return booking

    except:
        if booking: 
            booking.delete()
        raise

def set_session_booking(session, booking):
    session['ps_booking'] = booking.id
    session.modified = True

def get_session_admissions_booking(session):
    if 'ad_booking' in session:
        booking_id = session['ad_booking']
    else:
        raise Exception('Admissions booking not in Session')

    try:
        return AdmissionsBooking.objects.get(id=booking_id)
    except AdmissionsBooking.DoesNotExist:
        raise Exception('Admissions booking not found for booking_id {}'.format(booking_id))

def get_annual_admission_session_booking(session):
    if 'annual_admission_booking' in session:
        booking_id = session['annual_admission_booking']
    else:
        raise Exception('Annual Admission Booking not in Session')

    try:
        return BookingAnnualAdmission.objects.get(id=booking_id)
    except BookingAnnualAdmission.DoesNotExist:
        raise Exception('Annual Admission Booking not found for booking_id {}'.format(booking_id))

def delete_annual_admission_session_booking(session):
    if 'annual_admission_booking' in session:
        del session['annual_admission_booking']
        session.modified = True

def delete_session_admissions_booking(session):
    if 'ad_booking' in session:
        del session['ad_booking']
        session.modified = True

def get_session_booking(session):
    if 'ps_booking' in session:
        booking_id = session['ps_booking']
    else:
        raise Exception('Booking not in Session')

    try:
        return Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        raise Exception('Booking not found for booking_id {}'.format(booking_id))

def delete_session_booking(session):
    if 'ps_booking' in session:
        del session['ps_booking']
        session.modified = True

def daterange(start_date, end_date):
    for n in range(int ((end_date - start_date).days)):
        yield start_date + timedelta(n)


def oracle_integration(date,override):
    system = '0516'
    oracle_codes = oracle_parser_on_invoice(date,system,'Mooring Booking',override=override)

def admissions_lines(booking_mooring):
    lines = []
    for bm in booking_mooring:
        # Convert the from and to dates of this booking to just plain dates in local time.
        # Append them to a list.
        if bm.campsite.mooringarea.park.entry_fee_required:
            from_dt = bm.from_dt
            timestamp = calendar.timegm(from_dt.timetuple())
            local_dt = datetime.fromtimestamp(timestamp)
            from_dt = local_dt.replace(microsecond=from_dt.microsecond)
            to_dt = bm.to_dt
            timestamp = calendar.timegm(to_dt.timetuple())
            local_dt = datetime.fromtimestamp(timestamp)
            to_dt = local_dt.replace(microsecond=to_dt.microsecond)
            group = MooringAreaGroup.objects.filter(moorings__in=[bm.campsite.mooringarea,])[0].id
            lines.append({'from': from_dt, 'to': to_dt, 'group':group})
    # Sort the list by date from.
    new_lines = sorted(lines, key=lambda line: line['from'])
    i = 0
    lines = []
    latest_from = None
    latest_to = None
    # Loop through the list, if first instance, then this line's from date is the first admission fee.
    # Then compare this TO value to the next FROM value. If they are not the same or overlapping dates
    # add this date to the list, using the latest from and this TO value.
    while i < len(new_lines):
        if i == 0:
            latest_from = new_lines[i]['from'].date()
        if i < len(new_lines)-1:
            if new_lines[i]['to'].date() < new_lines[i+1]['from'].date():
                latest_to = new_lines[i]['to'].date()
        else:
            # if new_lines[i]['from'].date() > new_lines[i-1]['to'].date():
            latest_to = new_lines[i]['to'].date()
        
        if latest_to:
            lines.append({"rowid":'admission_fee_id'+str(i), 'id': i,'from':datetime.strftime(latest_from, '%d %b %Y'), 'to': datetime.strftime(latest_to, '%d %b %Y'), 'admissionFee': 0, 'group': new_lines[i]['group']})
            if i < len(new_lines)-1:
                latest_from = new_lines[i+1]['from'].date()
                latest_to = None
        i+= 1
    return lines

# Access Level check for Group   
def mooring_group_access_level_change(pk,request):
     mooring_groups = MooringAreaGroup.objects.filter(members__in=[request.user,])
     if request.user.is_superuser is True:
          return True
     else:
          if ChangeGroup.objects.filter(pk=pk,mooring_group__in=mooring_groups).count() > 0:
              return True

     return False

def mooring_group_access_level_cancel(pk,request):
     mooring_groups = MooringAreaGroup.objects.filter(members__in=[request.user,])
     if request.user.is_superuser is True:
          return True
     else:
          if CancelGroup.objects.filter(pk=pk,mooring_group__in=mooring_groups).count() > 0:
              return True

     return False

def mooring_group_access_level_change_options(cg,pk,request):
     mooring_groups = MooringAreaGroup.objects.filter(members__in=[request.user,])
     if request.user.is_superuser is True:
          return True
     else:
          cpp = ChangePricePeriod.objects.get(id=pk)
          if ChangeGroup.objects.filter(id=cg,change_period__in=[cpp],mooring_group__in=mooring_groups).count() > 0:
              return True

     return False

def mooring_group_access_level_cancel_options(cg,pk,request):
     mooring_groups = MooringAreaGroup.objects.filter(members__in=[request.user,])
     if request.user.is_superuser is True:
          return True
     else:
          cpp = CancelPricePeriod.objects.get(id=pk)
          if CancelGroup.objects.filter(id=cg,cancel_period__in=[cpp],mooring_group__in=mooring_groups).count() > 0:
              return True

     return False
 
def mooring_group_access_level_booking_period(pk,request):
     mooring_groups = MooringAreaGroup.objects.filter(members__in=[request.user,])
     if request.user.is_superuser is True:
          return True
     else:
          if BookingPeriod.objects.filter(pk=pk,mooring_group__in=mooring_groups).count() > 0:
              return True
    
     return False

def mooring_group_access_level_annual_booking_period(pk,request):
     mooring_groups = MooringAreaGroup.objects.filter(members__in=[request.user,])
     if request.user.is_superuser is True:
          return True
     else:
          if models.AnnualBookingPeriodGroup.objects.filter(pk=pk,mooring_group__in=mooring_groups).count() > 0:
              return True

     return False


def mooring_group_access_level_booking_period_option(pk,bp_group_id,request):
     mooring_groups = MooringAreaGroup.objects.filter(members__in=[request.user,])
     if request.user.is_superuser is True:
          return True
     else:
          bpo = BookingPeriodOption.objects.get(id=pk)
          if BookingPeriod.objects.filter(pk=bp_group_id,booking_period__in=[bpo],mooring_group__in=mooring_groups).count() > 0:
              return True
     return False


def check_mooring_admin_access(request): 
    if request.user.is_superuser is True:
        return True
    else:
      if request.user.groups.filter(name__in=['Mooring Admin']).exists():
          return True
    return False


def get_provinces(country_code):
    provinces = []
    read_data = ""
    json_response = []
    with io.open(settings.BASE_DIR+'/mooring/data/provinces.json', "r", encoding="utf-8") as my_file:
             read_data = my_file.read()
    provinces = json.loads(read_data)

    for p in provinces:
        if p['country'] == country_code:
            if 'short' in p:
               json_response.append(p)

    return json_response




def booking_success(basket, booking, context_processor):

    print("MLINE 1.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    order = Order.objects.get(basket=basket[0])
    invoice = Invoice.objects.get(order_number=order.number)
    print("MLINE 1.02", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    invoice_ref = invoice.reference
    book_inv, created = BookingInvoice.objects.get_or_create(booking=booking, invoice_reference=invoice_ref)
    print("MLINE 1.03", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    #invoice_ref = request.GET.get('invoice')
    if booking.booking_type == 3:
        print("MLINE 2.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        try:
            inv = Invoice.objects.get(reference=invoice_ref)
            order = Order.objects.get(number=inv.order_number)
            order.user = booking.customer
            order.save()
        except Invoice.DoesNotExist:
            print ("INVOICE ERROR")
            logger.error('{} tried making a booking with an incorrect invoice'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user'))
            return redirect('public_make_booking')
        if inv.system not in ['0516']:
            print ("SYSTEM ERROR")
            logger.error('{} tried making a booking with an invoice from another system with reference number {}'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user',inv.reference))
            return redirect('public_make_booking')
        print("MLINE 3.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        if book_inv:
            print("MLINE 4.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            if booking.old_booking:
                old_booking = Booking.objects.get(id=booking.old_booking.id)
                old_booking.booking_type = 4
                old_booking.cancelation_time = datetime.now()
                old_booking.canceled_by = booking.created_by #request.user
                old_booking.save()
                booking_items = MooringsiteBooking.objects.filter(booking=old_booking)
                # Find admissions booking for old booking
                if old_booking.admission_payment:
                    old_booking.admission_payment.booking_type = 4
                    old_booking.admission_payment.cancelation_time = datetime.now()
                    old_booking.admission_payment.canceled_by = booking.created_by #request.user
                    old_booking.admission_payment.save()
                for bi in booking_items:
                    bi.booking_type = 4
                    bi.save()
            print("MLINE 5.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            booking_items_current = MooringsiteBooking.objects.filter(booking=booking)
            for bi in booking_items_current:
               if str(bi.id) in booking.override_lines:
                  bi.amount = Decimal(booking.override_lines[str(bi.id)])
               bi.save()
            print("MLINE 6.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            msb = MooringsiteBooking.objects.filter(booking=booking).order_by('from_dt')
            from_date = msb[0].from_dt
            to_date = msb[msb.count()-1].to_dt
            timestamp = calendar.timegm(from_date.timetuple())
            local_dt = datetime.fromtimestamp(timestamp)
            from_dt = local_dt.replace(microsecond=from_date.microsecond)
            from_date_converted = from_dt.date()
            timestamp = calendar.timegm(to_date.timetuple())
            local_dt = datetime.fromtimestamp(timestamp)
            to_dt = local_dt.replace(microsecond=to_date.microsecond)
            to_date_converted = to_dt.date()
            booking.arrival = from_date_converted
            booking.departure = to_date_converted
            # set booking to be permanent fixture
            booking.booking_type = 1  # internet booking
            booking.expiry_time = None
            print("MLINE 7.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            update_payments(invoice_ref)
            print("MLINE 8.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            #Calculate Admissions and create object
            if booking.admission_payment:
                 ad_booking = AdmissionsBooking.objects.get(pk=booking.admission_payment.pk)
                 #if request.user.__class__.__name__ == 'EmailUser':
                 ad_booking.created_by = booking.created_by
                 ad_booking.booking_type=1
                 print("MLINE 8.02", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
                 ad_booking.save()
                 print("MLINE 8.03", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
                 ad_invoice = AdmissionsBookingInvoice.objects.get_or_create(admissions_booking=ad_booking, invoice_reference=invoice_ref)
                 print("MLINE 8.04", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

                 for al in ad_booking.override_lines.keys():
                     ad_line = AdmissionsLine.objects.get(id=int(al))
                     ad_line.cost = ad_booking.override_lines[str(al)]
                     ad_line.save()
                 print("MLINE 8.05", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
                # booking.admission_payment = ad_booking
            booking.save()
            print("MLINE 9.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            #if not request.user.is_staff:
            #    print "USER IS NOT STAFF."
            #request.session['ps_last_booking'] = booking.id
            #utils.delete_session_booking(request.session)
            # send out the invoice before the confirmation is sent if total is greater than zero
            #if booking.cost_total > 0:
            print("MLINE 10.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            try:
                emails.send_booking_invoice(booking,context_processor)
            except Exception as e:
                print ("Error Sending Invoice ("+str(booking.id)+") :"+str(e))
            # for fully paid bookings, fire off confirmation emaili
            #if booking.invoice_status == 'paid':
            print("MLINE 11.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            try:
                emails.send_booking_confirmation(booking,context_processor)
            except Exception as e:
                print ("Error Sending Booking Confirmation ("+str(booking.id)+") :"+str(e))
            print("MLINE 12.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            refund_failed = None
            if models.RefundFailed.objects.filter(booking=booking).count() > 0:
                refund_failed = models.RefundFailed.objects.filter(booking=booking)
            # Create/Update Vessel in VesselDetails Table
            print("MLINE 13.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            try:

                if models.VesselDetail.objects.filter(rego_no=booking.details['vessel_rego']).count() > 0:
                        vd = models.VesselDetail.objects.filter(rego_no=booking.details['vessel_rego'])
                        p = vd[0]
                        p.vessel_size=booking.details['vessel_size']
                        p.vessel_draft=booking.details['vessel_draft']
                        p.vessel_beam=booking.details['vessel_beam']
                        p.vessel_weight=booking.details['vessel_weight']
                        p.save()
                else:
                        models.VesselDetail.objects.create(rego_no=booking.details['vessel_rego'],
                                                       vessel_size=booking.details['vessel_size'],
                                                       vessel_draft=booking.details['vessel_draft'],
                                                       vessel_beam=booking.details['vessel_beam'],
                                                       vessel_weight=booking.details['vessel_weight']
                                                      )
                print("MLINE 14.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            except:
                print ("ERROR: create vesseldetails on booking success")

            context = {
              'booking': booking,
              'book_inv': [book_inv],
              'refund_failed' : refund_failed
            }
            print("MLINE 15.01", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            return context



def booking_annual_admission_success(basket, booking, context_processor):

    order = Order.objects.get(basket=basket[0])
    invoice = Invoice.objects.get(order_number=order.number)
    invoice_ref = invoice.reference
    book_inv, created = models.BookingAnnualInvoice.objects.get_or_create(booking_annual_admission=booking, invoice_reference=invoice_ref)

    #invoice_ref = request.GET.get('invoice')
    if booking.booking_type == 3:
        try:
            inv = Invoice.objects.get(reference=invoice_ref)
            order = Order.objects.get(number=inv.order_number)
            order.user = booking.customer
            order.save()
        except Invoice.DoesNotExist:
            print ("INVOICE ERROR")
            logger.error('{} tried making a booking with an incorrect invoice'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user'))
            return redirect('public_make_booking')
        if inv.system not in ['0516']:
            print ("SYSTEM ERROR")
            logger.error('{} tried making a booking with an invoice from another system with reference number {}'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user',inv.reference))
            return redirect('public_make_booking')

        if book_inv:
            # set booking to be permanent fixture
            booking.booking_type = 1  # internet booking
            booking.expiry_time = None
            update_payments(invoice_ref)
            #Calculate Admissions and create object
            booking.save()
            #if not request.user.is_staff:
            #    print "USER IS NOT STAFF."
            print ("SEND EMAIL")

            try:
                emails.send_annual_admission_booking_invoice(booking,context_processor)
            except Exception as e:
                print ("Error Sending Invoice ("+str(booking.id)+") :"+str(e))

            try:
                emails.send_new_annual_admission_booking_internal(booking,context_processor)
            except Exception as e:
                print ("Error Sending Booking Confirmation ("+str(booking.id)+") :"+str(e))

            # for fully paid bookings, fire off confirmation emaili
            #if booking.invoice_status == 'paid':
            context = {
              'booking': booking,
              'book_inv': [book_inv],
            }

            try:

                if models.VesselDetail.objects.filter(rego_no=booking.details['vessel_rego']).count() > 0:
                        vd = models.VesselDetail.objects.filter(rego_no=booking.details['vessel_rego'])
                        p = vd[0]
                        p.vessel_name=booking.details['vessel_name']
                        p.save()
            except:
                print ("ERROR: create vesseldetails on booking success")


            print ("COMPLETED SUCCESS")
            return context


def booking_admission_success(basket, booking, context_processor):

     arrival = models.AdmissionsLine.objects.filter(admissionsBooking=booking)[0].arrivalDate
     overnight = models.AdmissionsLine.objects.filter(admissionsBooking=booking)[0].overnightStay

     order = Order.objects.get(basket=basket[0])
     invoice = Invoice.objects.get(order_number=order.number)
     invoice_ref = invoice.reference

     #invoice_ref = request.GET.get('invoice')

     if booking.booking_type == 3:
         try:
             inv = Invoice.objects.get(reference=invoice_ref)
             order = Order.objects.get(number=inv.order_number)
             order.user = booking.customer
             order.save()
         except Invoice.DoesNotExist:
             logger.error('{} tried making a booking with an incorrect invoice'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user'))
             return redirect('admissions', args=(booking.location.key,))

         if inv.system not in ['0516']:
             logger.error('{} tried making a booking with an invoice from another system with reference number {}'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user',inv.reference))
             return redirect('admissions', args=(booking.location.key,))

         try:
             b = AdmissionsBookingInvoice.objects.get(invoice_reference=invoice_ref)
             logger.error('{} tried making an admission booking with an already used invoice with reference number {}'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user',inv.reference))
             return redirect('admissions',  args=(booking.location.key,))
         except AdmissionsBookingInvoice.DoesNotExist:
             logger.info('{} finished temporary booking {}, creating new AdmissionBookingInvoice with reference {}'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user',booking.id, invoice_ref))
             # FIXME: replace with server side notify_url callback
             admissionsInvoice = AdmissionsBookingInvoice.objects.get_or_create(admissions_booking=booking, invoice_reference=invoice_ref)
             #if request.user.__class__.__name__ == 'EmailUser':
             #    booking.created_by = request.user

             # set booking to be permanent fixture
             booking.booking_type = 1  # internet booking
             booking.save()
             #request.session['ad_last_booking'] = booking.id
             #utils.delete_session_admissions_booking(request.session)

             try:
                 # send out the invoice before the confirmation is sent
                 emails.send_admissions_booking_invoice(booking,context_processor) 
             except Exception as e:
                 print ("Error Sending Invoice ("+str(booking.id)+") :"+str(e))

             try:
                 # for fully paid bookings, fire off confirmation email
                 emails.send_admissions_booking_confirmation(booking,context_processor)
             except Exception as e:
                 print ("Error Sending Booking Confirmation ("+str(booking.id)+") :"+str(e))


             context = {
                'admissionsBooking': booking,
                'arrival' : arrival,
                'overnight': overnight,
                'admissionsInvoice': [invoice_ref]
             }

