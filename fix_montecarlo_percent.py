from pathlib import Path

p = Path("templates/montecarlo.html")
s = p.read_text(encoding="utf-8")

replacements = {
    'Default consigliato: 30%.': 'Default consigliato: 30%%.',
    'scenario peggiore tra il 5% finale delle simulazioni': 'scenario peggiore tra il 5%% finale delle simulazioni',
    'scenario migliore tra il 5% finale delle simulazioni': 'scenario migliore tra il 5%% finale delle simulazioni',
    'Inserisci una soglia di rovina valida (1% - 95%)': 'Inserisci una soglia di rovina valida (1%% - 95%%)',
    'Ulcer Index % nella sezione Equity-Based': 'Ulcer Index %% nella sezione Equity-Based',
    'Probability of Ruin % nella sezione Equity-Based': 'Probability of Ruin %% nella sezione Equity-Based',
    'peggior 5% dei risultati finali': 'peggior 5%% dei risultati finali',
    'Con soglia 30%,': 'Con soglia 30%%,',
    '10-15% = molto severo; 20-30% = prudente; 40-50% = permissivo': '10-15%% = molto severo; 20-30%% = prudente; 40-50%% = permissivo',
    'sotto 5% = contenuto; 5-15% = moderato; 15-25% = importante; oltre 25% = elevato': 'sotto 5%% = contenuto; 5-15%% = moderato; 15-25%% = importante; oltre 25%% = elevato',
    'sotto 10% = gestibile; 10-25% = rilevante; oltre 25-30% = molto impegnativo': 'sotto 10%% = gestibile; 10-25%% = rilevante; oltre 25-30%% = molto impegnativo',
    'Valore finale sotto cui cade il peggior 5% degli scenari bootstrap': 'Valore finale sotto cui cade il peggior 5%% degli scenari bootstrap',
}

for old, new in replacements.items():
    s = s.replace(old, new)

p.write_text(s, encoding="utf-8")
print("OK - montecarlo.html percentuali escape %% applicate")
