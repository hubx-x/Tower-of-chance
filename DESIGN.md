# Towers of chance

## 1. Nosaukums un žanrs
**Towers of chance** ir vienkārša 2D torņu aizsardzības (tower defense) spēle Python un Pygame vidē ar vienu karti un vienu torņa veidu. Galvenajā izvēlnē var pieteikties ar spēlētāja vārdu, sākt spēli un apskatīt rekordus.

## 2. Mērķis
Aizsargāt bāzi un izturēt trīs līmeņus, katrā pa trim ienaidnieku viļņiem. Bāzei sākumā ir 20 dzīvības, un katrs garām ticis ienaidnieks atņem vienu dzīvību. Spēlētājs uzvar pēc devītā viļņa, ja bāzei vēl ir dzīvības, un zaudē, ja tās sasniedz nulli. Beigās parādās rezultāta ekrāns ar punktiem.

## 3. Vadība
- **Kreisā peles poga** — izvēlēties, novietot un uzlabot torni, izvēlēties efektu; ar pogu “Apvienot” izvēlēties divus saderīgus torņus.
- **Labā peles poga** — atcelt izvēli.
- **Space** — sākt nākamo vilni.
- **P** — ieslēgt vai izslēgt pauzi.
- **Esc** — atgriezties galvenajā izvēlnē.

## 4. Pamata cikls
Spēlētājs par monētām novieto torņus un sāk vilni. Torņi automātiski šauj uz ienaidniekiem, un par uzvarētiem ienaidniekiem spēlētājs saņem monētas. Starp viļņiem viņš izvēlas vienu nejaušo efektu, pērk vai uzlabo torņus un gatavojas nākamajam vilnim.

## 5. Divas īpašās mehānikas
1. Starp viļņiem spēlētājs saņem trīs nejaušus efektus, kas palielina vai samazina torņu bojājumus, šaušanas ātrumu vai darbības rādiusu, un izvēlas tikai vienu.
2. Katram tornim ir trīs uzlabošanas ceļi (bojājumi, šaušanas ātrums vai rādiuss), spēlētājs izvēlas vienu ceļu līdz 3. līmenim un var apvienot divus šī ceļa 3. līmeņa torņus vienā 4. līmeņa tornī.

## 6. Līmeņi
Visos trīs līmeņos izmanto vienu karti, katrā ir trīs viļņi:
- **1. līmenis:** 5 ienaidnieki vilnī, katram 10 dzīvības.
- **2. līmenis:** 8 ienaidnieki vilnī, katram 15 dzīvības.
- **3. līmenis:** 12 ienaidnieki vilnī, katram 20 dzīvības.

Torņi, monētas un atlikušās bāzes dzīvības pāriet uz nākamo līmeni.

## 7. Punkti
Par uzvarētu ienaidnieku saņem 10 punktus, par pabeigtu vilni 50 punktus un par pabeigtu līmeni 100 punktus. Punkti veido gala rezultātu, bet torņu iegādei izmanto atsevišķas monētas.

## 8. Saglabāšana un ielāde
Spēles beigās serverī saglabā spēlētāja vārdu, iegūtos punktus un sasniegto līmeni. Izvēlnē ielādē personīgo rekordu un labāko rezultātu tabulu. Jaunu spēli sāk no pirmā līmeņa.
