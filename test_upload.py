import requests

url = "http://127.0.0.1:5000/api/montecarlo/upload"

file_path = r"C:\Users\andre\Documents\ReportTester-68287006.html"  # cambia se vuoi testare xlsx

with open(file_path, "rb") as f:
    files = {"file": f}
    res = requests.post(url, files=files)

print("STATUS:", res.status_code)
print("RESPONSE:", res.text)