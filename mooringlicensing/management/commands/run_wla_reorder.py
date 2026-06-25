from django.core.management.base import BaseCommand
from mooringlicensing.components.main.utils import reorder_wla
from mooringlicensing.components.proposals.models import MooringBay

class Command(BaseCommand):
    def handle(self, *args, **options):
       
        active_bays = MooringBay.objects.filter(active=True)
        #iterate through bays, run reorder
        for bay in active_bays:
            reorder_wla(bay)