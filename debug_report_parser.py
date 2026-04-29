import sys
import pandas as pd

path = sys.argv[1]

print("FILE:", path)

if path.lower().endswith(".html"):
    raw = open(path, "rb").read()

    for enc in ["utf-16le", "utf-8", "latin1"]:
        try:
            html = raw.decode(enc, errors="ignore")
            tables = pd.read_html(html)
            print("\nENCODING:", enc)
            print("TABELLE:", len(tables))

            for i, df in enumerate(tables):
                print("\n--- TABLE", i, "SHAPE", df.shape, "---")
                print(df.head(15).to_string())
            break
        except Exception as e:
            print("FAIL", enc, e)

elif path.lower().endswith(".xlsx"):
    xls = pd.ExcelFile(path)
    print("SHEETS:", xls.sheet_names)

    for sheet in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        print("\n--- SHEET", sheet, "SHAPE", df.shape, "---")
        print(df.head(30).to_string())

else:
    print("Formato non supportato")