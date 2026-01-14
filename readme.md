# WIJ Groningen agent

## functionaliteiten
- afvangen van naar een persoon herleidbare gegevens (todo)
- invoer en uitvoer worden opgeslagen tbv trainingsdoeleinden en privacy breaches
- transparantie: alle documenten die gebruikt worden voor de agent zijn publiekelijk beschikbaar


## CoPilot vs Build
- Build kan invoer en uitvoer opslaan
- Build kan beheerst persoonsgegevens afvangen (en loggen)
- Build kan uitgebouwd worden naar een 'interne google'
- Build draait op een Europees model (Mistral)
- Build vraag beheerskosten en kennis


## Tokens mij MistralAI
Een token is ongeveer 4 tekens. 100 tokens komen overeen met ongeveer 75 woorden.

Hier zijn de actuele tarieven voor januari 2026:

Mistral Large 2411: $0,002 per 1.000 input tokens en $0,006 per 1.000 output tokens. Dat komt neer op $2 per miljoen input tokens en $6 per miljoen output tokens.
Mistral Medium 3: $0,40 per miljoen input tokens en $2 per miljoen output tokens, ofwel $0,0004 per 1.000 input tokens en $0,002 per 1.000 output tokens.

Dus uitgaande van gemiddeld 250 nieuwe jeugdtrajecten per maand, dus 3000 per jaar 
input = 750 (schatting), dus (750/75*100) = 1000 tokens
output = 2500 worden, dus (2.500/75*100)=3.333 tokens

dus:
3000 * 1000 = 3mln inputtokens, dus $1,20
3000 * 3.333 = 10mln outputtokens, dus 20 euro

Scheelt nogal met Copilot: 30 euro per maand per gebruiker, dus 30 * 12 * 1000 = 36.000 euro...