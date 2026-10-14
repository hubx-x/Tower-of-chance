# Towers of Chance

## 1. Nosaukums un žanrs

**Towers of Chance** ir vienkārša 2D torņu aizsardzības spēle Python un Pygame vidē ar pikseļu izskatu. Virsrakstiem izmanto VT323 fontu, pārējam tekstam — Windows iebūvēto Arial fontu vismaz 20 pikseļu izmērā. Spēlētājs novieto torņus blakus ienaidnieku ceļam. Galvenajā izvēlnē var ievadīt vārdu, izvēlēties grūtību un vienu no trim kartēm — Meadow, Desert vai Tundra —, sākt spēli, atvērt palīdzību un apskatīt rekordus.

## 2. Mērķis

Aizsargāt bāzi ar 20 dzīvībām un izturēt 3 līmeņus, katrā pārvarot 3 viļņus. Katrs ienaidnieks, kas sasniedz bāzi, atņem vienu dzīvību. Kad dzīvības beidzas, spēle rāda zaudējuma ekrānu; pēc devītā viļņa — uzvaras ekrānu ar rezultātu.

## 3. Vadība

Kreisais peles klikšķis izvēlas pogas, torņa veidu veikalā un tā novietošanas vietu, izvēlas esošus torņus, iegādājas uzlabojumus un izvēlas efekta kartīti. Labais klikšķis atceļ izvēli. **Space** sāk nākamo vilni, **P** ieslēdz vai izslēdz pauzi, **Esc** atgriež galvenajā izvēlnē. Apvienojot torņus, spēlētājs vispirms izvēlas vienu piemērotu torni un pēc tam otru.

Poga **Auto wave** ieslēdz vai izslēdz automātisku viļņu sākšanu; sākumā tā ir izslēgta, bet atkārtojot spēli, izvēle saglabājas. Izvēlētā torņa panelī **Sell** pārdod torni.

## 4. Pamata cikls

Spēlētājs izmanto monētas, lai novietotu torņus, un sāk vilni. Torņi šauj automātiski, bet uzvarētie ienaidnieki dod monētas un punktus. Starp viļņiem var būvēt un uzlabot torņus. Noteiktos viļņos spēle arī piedāvā izvēlēties vienu nejaušu efektu. Monētas, torņi un bāzes dzīvības pāriet uz nākamo līmeni.

Veikalā ir četri uzlabojami torņu veidi: Basic par 50 monētām, Ice par 80 ar īslaicīgu sasaldēšanu, Fire par 90 ar degšanas bojājumiem un Machine gun par 100 ar ātru šaušanu īsākā attālumā.

Basic šauj lielgabala lodes, Ice — ledus šķembas, Fire — ugunsbumbas, Machine gun — mazas, ātras lodes. Šāviņi lido no torņa līdz mērķim. Sasaldēšanu parāda ledus pārklājums, degšanu — liesmas uz ienaidnieka.

Ar ieslēgtu Auto wave nākamais vilnis sākas pēc 3 sekundēm gatavošanās režīmā, ja ir vismaz viens tornis. Pauze un gaidīšana uz kartītes izvēli aptur atskaiti. Slēdža maiņa, manuāls viļņa sākums un kartītes izvēle atiestata atskaiti uz 3 sekundēm. Ja visi torņi pārdoti, automātika gaida, līdz novietots cits tornis.

Pārdodot torni, atgūst 50% no tā cenas un par uzlabojumiem samaksātajām monētām, noapaļojot uz leju. Basic par 50 monētām atdod 25; uzlabots Basic par kopā 85 monētām atdod 42. Apvienota torņa pārdošanas summā ieskaita abu sākotnējo torņu ieguldījumus.

```text
+----------------------------------------------------------+
| Towers of Chance   LVL 1/3   WAVE 1/3   HP 20   SCORE 0    |
+----------------------------------------+-----------------+
|                                        | Coins           |
|   Entry ------+        [Tower]          | Basic / Ice     |
|               |                        | Fire / M. gun   |
|       [Tower] +----------+              |                 |
|                         |              | Selected tower  |
|              [Tower]    +------ Base    | Damage / Speed  |
|                                        | Range           |
|                                        | Merge / Sell    |
+----------------------------------------+-----------------+
| Space: next wave    Auto: on/off    P: pause   Esc: menu    |
+----------------------------------------------------------+
```

## 5. Divas īpašās mehānikas

**Nejaušā izvēle.** Easy un Normal režīmā pēc kopējā 1., 4. un 7. viļņa parādās 3 nejaušas kartītes. Hard režīmā izvēle parādās pēc 1. un 6. viļņa. Kartītes, piemēram, palielina vai samazina torņu bojājumus, šaušanas ātrumu vai rādiusu. Spēlētājs izvēlas tikai vienu kartīti, un tās efekts saglabājas pārējos viļņos. Pēc devītā viļņa uzreiz parādās uzvaras ekrāns.

**Uzlabojumi un apvienošana.** Visiem četriem torņu veidiem ir 3 uzlabojumu ceļi: bojājumi, šaušanas ātrums un darbības rādiuss. Pirmais uzlabojums izvēlas ceļu; to var attīstīt līdz 3. līmenim. Uzlabojums uz 2. līmeni maksā 35 monētas, bet uz 3. līmeni — 65. Divus viena veida 3. līmeņa torņus ar vienādu ceļu var bez maksas apvienot vienā 4. līmeņa tornī.

## 6. Līmeņi un grūtība

Pirms spēles var izvēlēties Meadow (pļava), Desert (tuksnesis) vai Tundra (tundra). Katrai kartei ir savs ienaidnieku ceļš un izskats. Izvēlētā karte paliek tā pati visos trīs līmeņos; katrā līmenī ir 3 viļņi. Normal grūtībā:

| Līmenis | Ienaidnieki katrā vilnī | Ienaidnieka dzīvības |
| --- | ---: | ---: |
| 1 | 5 | 10 |
| 2 | 8 | 15 |
| 3 | 12 | 20 |

Easy sākas ar 180 monētām, izmanto 4, 7 un 10 ienaidniekus ar 8, 12 un 16 dzīvībām, un ienaidnieku ātrums ir 85% no Normal. Normal sākas ar 150 monētām. Hard sākas ar 130 monētām, izmanto 7, 10 un 15 ienaidniekus ar 14, 21 un 28 dzīvībām, un ātrums ir 125% no Normal. Hard ienaidnieki parādās arī biežāk.

Uzlabojumi saglabājas visu 9 viļņu laikā. Ar izslēgtu Auto wave spēlētājs pats sāk nākamo vilni, kad ir pabeidzis būvēt un pārdomājis izvēles.

## 7. Punkti

Par katru uzvarētu ienaidnieku piešķir 10 punktus, par pabeigtu vilni 50 un par pabeigtu līmeni 100. Punkti veido gala rezultātu. Monētas ir atsevišķs resurss, kuru izmanto torņu iegādei un uzlabojumiem.

## 8. Saglabāšana un ielāde

Spēles beigās lokālā JSON failā saglabā spēlētāja vārdu, punktus, sasniegto līmeni, grūtību, datumu un uzvaras vai zaudējuma statusu. Galvenajā izvēlnē var apskatīt personīgo labāko rezultātu un rekordu tabulu. Jauna spēle sākas no pirmā līmeņa; saglabātā rezultāta ieraksts neatjauno nepabeigtu spēli.
