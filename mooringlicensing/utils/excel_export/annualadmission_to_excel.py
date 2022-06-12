import pandas as pd


def write(filename):
    """
        from mooringlicensing.utils.excel_export.annualadmission_to_excel import write
        df = write()
    """
    df = pd.read_csv(filename)
    df.to_excel('annualadmission.xlsx', index=0)
    return df


