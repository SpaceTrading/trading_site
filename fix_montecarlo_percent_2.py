from pathlib import Path

p = Path("templates/montecarlo.html")
s = p.read_text(encoding="utf-8")

replacements = {
    "sotto 2% = molto basso; 2-5% = contenuto; 5-10% = moderato; oltre 10% = stressante.":
    "sotto 2%% = molto basso; 2-5%% = contenuto; 5-10%% = moderato; oltre 10%% = stressante.",

    "0% = ottimo sul campione simulato; 0-1% = basso; 1-5% = da monitorare; oltre 5% = critico.":
    "0%% = ottimo sul campione simulato; 0-1%% = basso; 1-5%% = da monitorare; oltre 5%% = critico.",
}

for old, new in replacements.items():
    s = s.replace(old, new)

p.write_text(s, encoding="utf-8")
print("OK - fix residue linee 254/255 applicata")
