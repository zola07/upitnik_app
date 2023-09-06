import os
import io
from flask import Flask, render_template, request, redirect, url_for, session, make_response, send_from_directory
import sqlite3
import uuid
from datetime import datetime
from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from flask import send_file
from datetime import timedelta
from fpdf import FPDF

app = Flask(__name__)

# Definišite UPLOAD_FOLDER i postavite dozvole za pisanje
UPLOAD_FOLDER = 'pdf_odgovori'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    os.chmod(UPLOAD_FOLDER, 0o777)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf'}

# Postavite nasumičan ključ za sesije
app.secret_key = os.urandom(24)

# Postavljanje trajanja sesije na 120 minuta (2 sata)
app.permanent_session_lifetime = timedelta(minutes=120)

# Funkcija za generisanje jedinstvenog ID-a
def kreiraj_jedinstveni_id():
    return str(uuid.uuid4())

# Funkcija za kreiranje tabele odgovora u bazi podataka
def kreiraj_bazu():
    with sqlite3.connect('upitnik.db') as conn:
        cursor = conn.cursor()
        # Provera da li tabela "odgovori" već postoji
        # Kreiranje tabele "korisnici" ako ne postoji
        cursor.execute('''CREATE TABLE IF NOT EXISTS korisnici (
                            id INTEGER PRIMARY KEY,
                            jedinstveni_id TEXT NOT NULL,
                            ime_prezime TEXT NOT NULL,
                            maticni_broj TEXT,
                            adresa TEXT NOT NULL,
                            email TEXT NOT NULL,
                            kontakt TEXT,
                            svrha_popunjavanja TEXT NOT NULL
                          )''')
        
        # Kreiranje tabele "odgovori" ako ne postoji
        cursor.execute('''CREATE TABLE IF NOT EXISTS odgovori (
                            id INTEGER PRIMARY KEY,
                            jedinstveni_id TEXT NOT NULL,
                            pitanje TEXT, 
                            naslov_pitanje TEXT,  -- Dodajemo kolonu za naslov pitanja    
                            odgovor TEXT,
                            odgovor_text TEXT,
                            odgovor_checkbox TEXT
                          )''')
        conn.commit()

# Pozivamo funkciju za kreiranje tabele ako baza podataka ne postoji
if not os.path.exists('upitnik.db'):
    kreiraj_bazu()

def dohvati_odgovore_korisnika(jedinstveni_id):
    with sqlite3.connect('upitnik.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT pitanje, odgovor, odgovor_text FROM odgovori WHERE jedinstveni_id = ?', (jedinstveni_id,))
        return cursor.fetchall()

def dodaj_odgovor(jedinstveni_id, pitanje, odgovor, odgovor_text=None, odgovor_checkbox=None):
    with sqlite3.connect('upitnik.db') as conn:
        cursor = conn.cursor()

        # Provera da li je odgovor checkbox polje
        if isinstance(odgovor, list):
            # Ako jeste, sačuvajte svaku izabranu opciju u bazi podataka
            for opcija in odgovor:
                # Takođe, čuvamo i odgovor_checkbox koji će sadržati string sa svim izabranim opcijama odvojenim zarezima
                cursor.execute('INSERT INTO odgovori (jedinstveni_id, pitanje, odgovor, odgovor_checkbox) VALUES (?, ?, ?, ?)',
                               (jedinstveni_id, pitanje, opcija, ','.join(odgovor)))
        else:
            # Ako nije, to znači da je odgovor radio button ili tekst polje, pa ga sačuvajte kao i do sada
            cursor.execute('INSERT INTO odgovori (jedinstveni_id, pitanje, odgovor, odgovor_text) VALUES (?, ?, ?, ?)',
                           (jedinstveni_id, pitanje, odgovor, odgovor_text))

        conn.commit()
        
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        ime_prezime = request.form['ime_prezime']
        maticni_broj = request.form['maticni_broj']
        adresa = request.form['adresa']
        email = request.form['email']
        kontakt = request.form['kontakt']
        svrha_popunjavanja = request.form['svrha_popunjavanja']

        # Generisanje jedinstvenog ID-a i postavljanje u cookie kako bi se koristio tokom upitnika
        jedinstveni_id = kreiraj_jedinstveni_id()
        response = make_response(redirect(url_for('upitnik')))
        response.set_cookie('jedinstveni_id', jedinstveni_id)
        return response

    return render_template('index.html')

@app.route('/upitnik', methods=['GET', 'POST'])
def upitnik():
    if 'jedinstveni_id' in request.cookies:
        # Ako postoji jedinstveni ID u sessionu, koristimo ga
        jedinstveni_id = request.cookies['jedinstveni_id']
    else: 
        # Ako ne postoji jedinstveni ID u sessionu, korisnik nije pravilno započeo upitnik, preusmeravamo ga na početnu stranicu
        return redirect(url_for('index'))
       
    return render_template('upitnik.html', jedinstveni_id=jedinstveni_id)

def izracunaj_ukupan_broj_stranica():
    # Funkcija koja vraća ukupan broj stranica upitnika (npr. 5)
    return 7

def izracunaj_napredak(trenutna_stranica, ukupan_broj_stranica):
    # Implementirajte logiku za izračunavanje procenta napretka
    progres = trenutna_stranica / ukupan_broj_stranica * 100
    return "{:.2f}".format(progres)  # Formatiramo procenat sa dve decimale
  
@app.route('/delovanje_i_kontrola', methods=['GET', 'POST'])
def delovanje_i_kontrola():
    if 'jedinstveni_id' in request.cookies:
        jedinstveni_id = request.cookies['jedinstveni_id']
    else:
        return redirect(url_for('index'))

    # Inicijalizujemo sesiju i postavljamo trenutnu stranicu na 1 ako nije postavljena
    session['trenutna_stranica'] = 1

    if request.method == 'POST':
        # Sačuvajte odgovore u sesiji koristeći ključeve koji će biti jedinstveni za svako pitanje
        session['pitanje1'] = request.form.get('pitanje1', '')
        session['pitanje2'] = request.form.get('pitanje2', '')
        session['pitanje2_text'] = request.form.get('pitanje2_text_odgovor', '')
        session['pitanje3'] = request.form.get('pitanje3', '')
        session['pitanje3_text'] = request.form.get('pitanje3_text_odgovor', '')
        session['pitanje4'] = request.form.get('pitanje4', '')
        session['pitanje5'] = request.form.get('pitanje5', '')
        session['pitanje5_text'] = request.form.get('pitanje5_text_odgovor', '')
        session['pitanje6'] = request.form.get('pitanje6', '')
        session['pitanje6_text'] = request.form.get('pitanje6_text_odgovor', '')
        session['pitanje7'] = request.form.get('pitanje7', '')
        session['pitanje7_text'] = request.form.get('pitanje7_text_odgovor', '')
        session['pitanje8'] = request.form.get('pitanje8', '')
        session['pitanje8_text'] = request.form.get('pitanje8_text_odgovor', '')
        session['pitanje9'] = request.form.get('pitanje9', '')
        session['pitanje10'] = request.form.get('pitanje10', '')
        session['pitanje11'] = request.form.get('pitanje11', '')
        session['pitanje11_text'] = request.form.get('pitanje11_text_odgovor', '')
        session['pitanje12'] = request.form.get('pitanje12', '')
        session['pitanje12_text'] = request.form.get('pitanje12_text_odgovor', '')
        session['pitanje13'] = request.form.get('pitanje13', '')
        session['pitanje13_text'] = request.form.get('pitanje13_text_odgovor', '')

        # ...

        return redirect(url_for('delovanje_i_kontrola_preporuke'))

    # Ako postoje odgovori u sesiji, pre-popunite formu sa odgovarajućim vrednostima
    odgovor_pitanje1 = session.get('pitanje1', '')
    odgovor_pitanje2 = session.get('pitanje2', '')
    odgovor_pitanje2_text = session.get('pitanje2_text', '')
    odgovor_pitanje3 = session.get('pitanje3', '')
    odgovor_pitanje3_text = session.get('pitanje3_text', '')
    odgovor_pitanje4 = session.get('pitanje4', '')
    odgovor_pitanje5 = session.get('pitanje5', '')
    odgovor_pitanje5_text = session.get('pitanje5_text', '')
    odgovor_pitanje6 = session.get('pitanje6', '')
    odgovor_pitanje6_text = session.get('pitanje6_text', '')
    odgovor_pitanje7 = session.get('pitanje7', '')
    odgovor_pitanje7_text = session.get('pitanje7_text', '')
    odgovor_pitanje8 = session.get('pitanje8', '')
    odgovor_pitanje8_text = session.get('pitanje8_text', '')
    odgovor_pitanje9 = session.get('pitanje9', '')
    odgovor_pitanje10 = session.get('pitanje10', '')
    odgovor_pitanje11 = session.get('pitanje11', '')
    odgovor_pitanje11_text = session.get('pitanje11_text', '')
    odgovor_pitanje12 = session.get('pitanje12', '')
    odgovor_pitanje12_text = session.get('pitanje12_text', '')
    odgovor_pitanje13 = session.get('pitanje13', '')
    odgovor_pitanje13_text = session.get('pitanje13_text', '')

    trenutna_stranica = session.get('trenutna_stranica', 1)
    ukupan_broj_stranica = izracunaj_ukupan_broj_stranica()
    progres = izracunaj_napredak(trenutna_stranica, ukupan_broj_stranica)


    return render_template(
        'delovanje_i_kontrola.html',
        jedinstveni_id=jedinstveni_id, progres=progres,
        odgovor_pitanje1=odgovor_pitanje1,
        odgovor_pitanje2=odgovor_pitanje2,
        odgovor_pitanje2_text=odgovor_pitanje2_text,
        odgovor_pitanje3=odgovor_pitanje3,
        odgovor_pitanje3_text=odgovor_pitanje3_text,
        odgovor_pitanje4=odgovor_pitanje4,
        odgovor_pitanje5=odgovor_pitanje5,
        odgovor_pitanje5_text=odgovor_pitanje5_text,
        odgovor_pitanje6=odgovor_pitanje6,
        odgovor_pitanje6_text=odgovor_pitanje6_text,
        odgovor_pitanje7=odgovor_pitanje7,
        odgovor_pitanje7_text=odgovor_pitanje7_text,
        odgovor_pitanje8=odgovor_pitanje8,
        odgovor_pitanje8_text=odgovor_pitanje8_text,
        odgovor_pitanje9=odgovor_pitanje9,
        odgovor_pitanje10=odgovor_pitanje10,
        odgovor_pitanje11=odgovor_pitanje11,
        odgovor_pitanje11_text=odgovor_pitanje11_text,
        odgovor_pitanje12=odgovor_pitanje12,
        odgovor_pitanje12_text=odgovor_pitanje12_text,
        odgovor_pitanje13=odgovor_pitanje13,
        odgovor_pitanje13_text=odgovor_pitanje13_text,
    )

@app.route('/tehnicka_pouzdanost_i_bezbednost', methods=['GET', 'POST'])
def tehnicka_pouzdanost_i_bezbednost():
    # Provera da li korisnik ima jedinstveni ID u sessionu
    if 'jedinstveni_id' in request.cookies:
        # Ako postoji jedinstveni ID u sessionu, koristimo ga
        jedinstveni_id = request.cookies['jedinstveni_id']
    else:
        # Ako ne postoji jedinstveni ID u sessionu, korisnik nije pravilno započeo upitnik, preusmeravamo ga na početnu stranicu
        return redirect(url_for('index'))
    
    session['trenutna_stranica'] = 2

    if request.method == 'POST':
        # Provera akcije koju je korisnik izabrao (sledeća stranica ili prethodna stranica)
        action = request.form['action']

        if action == 'next':
           
            session['pitanje14'] = request.form.get('pitanje14', '')
            session['pitanje15'] = request.form.get('pitanje15', '')
            session['pitanje15_text'] = request.form.get('pitanje15_text_odgovor', '')
            session['pitanje16'] = request.form.get('pitanje16', '')
            session['pitanje16_text'] = request.form.get('pitanje16_text_odgovor', '')
            session['pitanje17'] = request.form.get('pitanje17', '')
            session['pitanje17_text'] = request.form.get('pitanje17_text_odgovor', '')
            session['pitanje18'] = request.form.getlist('pitanje18')
            session['pitanje18_text'] = request.form.get('pitanje18_text_odgovor', '')
            session['pitanje19'] = request.form.get('pitanje19', '')
            session['pitanje19_text'] = request.form.get('pitanje19_text_odgovor', '')
            session['pitanje20'] = request.form.get('pitanje20', '')
            session['pitanje20_text'] = request.form.get('pitanje20_text_odgovor', '')
            session['pitanje21'] = request.form.get('pitanje21', '')
            session['pitanje22'] = request.form.get('pitanje22', '')
            session['pitanje22_text'] = request.form.get('pitanje22_text_odgovor', '')
            session['pitanje23'] = request.form.get('pitanje23', '')
            session['pitanje24'] = request.form.get('pitanje24', '')
            session['pitanje24_text'] = request.form.get('pitanje24_text_odgovor', '')
            session['pitanje25'] = request.form.get('pitanje25', '')
            session['pitanje25_text'] = request.form.get('pitanje25_text_odgovor', '')
            session['pitanje26'] = request.form.get('pitanje26', '')
            session['pitanje26_text'] = request.form.get('pitanje26_text_odgovor', '')
            session['pitanje27'] = request.form.get('pitanje27', '')
            session['pitanje27_text'] = request.form.get('pitanje27_text_odgovor', '')
            session['pitanje28'] = request.form.get('pitanje28', '')
            session['pitanje29'] = request.form.get('pitanje29', '')
            session['pitanje29_text'] = request.form.get('pitanje29_text_odgovor', '')
            session['pitanje30'] = request.form.get('pitanje30', '')
            session['pitanje30_text'] = request.form.get('pitanje30_text_odgovor', '')
            session['pitanje31'] = request.form.get('pitanje31', '')
            session['pitanje31_text'] = request.form.get('pitanje31_text_odgovor', '')
            session['pitanje32'] = request.form.get('pitanje32', '')
            session['pitanje32_text'] = request.form.get('pitanje32_text_odgovor', '')
            session['pitanje33'] = request.form.get('pitanje33', '')
            session['pitanje33_text'] = request.form.get('pitanje33_text_odgovor', '')
            session['pitanje34'] = request.form.get('pitanje34', '')
            session['pitanje34_text'] = request.form.get('pitanje34_text_odgovor', '')
            session['pitanje35'] = request.form.get('pitanje35', '')
            session['pitanje35_text'] = request.form.get('pitanje35_text_odgovor', '')
            session['pitanje36'] = request.form.get('pitanje36', '')
            session['pitanje36_text'] = request.form.get('pitanje36_text_odgovor', '')
            session['pitanje37'] = request.form.get('pitanje37', '')
            session['pitanje37_text'] = request.form.get('pitanje37_text_odgovor', '')
            session['pitanje38'] = request.form.get('pitanje38', '')
            session['pitanje38_text'] = request.form.get('pitanje38_text_odgovor', '')
            session['pitanje39'] = request.form.get('pitanje39', '')
            session['pitanje40'] = request.form.get('pitanje40', '')
            session['pitanje40_text'] = request.form.get('pitanje40_text_odgovor', '')
            session['pitanje41'] = request.form.get('pitanje41', '')
            session['pitanje42'] = request.form.get('pitanje42', '')
            session['pitanje42_text'] = request.form.get('pitanje42_text_odgovor', '')
            


            # Ovde možete sačuvati odgovore u bazu podataka ili uraditi neku drugu obradu sa njima

            # Povećavamo trenutnu stranicu za 1
            session['trenutna_stranica'] += 1

            return redirect(url_for('tehnicka_pouzdanost_i_bezbednost_preporuke'))
            
        

        elif action == 'prev':
            # Ako je izabrana prethodna stranica, smanjujemo trenutnu stranicu za 1
            session['trenutna_stranica'] -= 1

            return redirect(url_for('delovanje_i_kontrola'))

            # Možete ovde dodati logiku za čuvanje prethodnih odgovora u bazi podataka ili neki drugi način čuvanja
    
        else:
            # Ako korisnik šalje neku drugu akciju, preusmeravamo ga na početnu stranicu
            return redirect(url_for('index'))
        
    odgovor_pitanje14 = session.get('pitanje14', '')
    odgovor_pitanje15 = session.get('pitanje15', '')
    odgovor_pitanje15_text = session.get('pitanje15_text', '')
    odgovor_pitanje16 = session.get('pitanje16', '')
    odgovor_pitanje16_text = session.get('pitanje16_text', '')
    odgovor_pitanje17 = session.get('pitanje17', '')
    odgovor_pitanje17_text = session.get('pitanje17_text', '')
    odgovor_pitanje18 = session.get('pitanje18', [])
    odgovor_pitanje18_text = session.get('pitanje18_text', '')
    odgovor_pitanje19 = session.get('pitanje19', '')
    odgovor_pitanje19_text = session.get('pitanje19_text', '')
    odgovor_pitanje20 = session.get('pitanje20', '')
    odgovor_pitanje20_text = session.get('pitanje20_text', '')
    odgovor_pitanje21 = session.get('pitanje21', '')
    odgovor_pitanje22 = session.get('pitanje22', '')
    odgovor_pitanje22_text = session.get('pitanje22_text', '')
    odgovor_pitanje23 = session.get('pitanje23', '')
    odgovor_pitanje24 = session.get('pitanje24', '')
    odgovor_pitanje24_text = session.get('pitanje24_text', '')
    odgovor_pitanje25 = session.get('pitanje25', '')
    odgovor_pitanje25_text = session.get('pitanje25_text', '')
    odgovor_pitanje26 = session.get('pitanje26', '')
    odgovor_pitanje26_text = session.get('pitanje26_text', '')
    odgovor_pitanje27 = session.get('pitanje27', '')
    odgovor_pitanje27_text = session.get('pitanje27_text', '')
    odgovor_pitanje28 = session.get('pitanje28', '')
    odgovor_pitanje29 = session.get('pitanje29', '')
    odgovor_pitanje29_text = session.get('pitanje29_text', '')
    odgovor_pitanje30 = session.get('pitanje30', '')
    odgovor_pitanje30_text = session.get('pitanje30_text', '')
    odgovor_pitanje31 = session.get('pitanje31', '')
    odgovor_pitanje31_text = session.get('pitanje31_text', '')
    odgovor_pitanje32 = session.get('pitanje32', '')
    odgovor_pitanje32_text = session.get('pitanje32_text', '')
    odgovor_pitanje33 = session.get('pitanje33', '')
    odgovor_pitanje33_text = session.get('pitanje33_text', '')
    odgovor_pitanje34 = session.get('pitanje34', '')
    odgovor_pitanje34_text = session.get('pitanje34_text', '')
    odgovor_pitanje35 = session.get('pitanje35', '')
    odgovor_pitanje35_text = session.get('pitanje35_text', '')
    odgovor_pitanje36 = session.get('pitanje36', '')
    odgovor_pitanje36_text = session.get('pitanje36_text', '')
    odgovor_pitanje37 = session.get('pitanje37', '')
    odgovor_pitanje37_text = session.get('pitanje37_text', '')
    odgovor_pitanje38 = session.get('pitanje38', '')
    odgovor_pitanje38_text = session.get('pitanje38_text', '')
    odgovor_pitanje39 = session.get('pitanje39', '')
    odgovor_pitanje40 = session.get('pitanje40', '')
    odgovor_pitanje40_text = session.get('pitanje40_text', '')
    odgovor_pitanje41 = session.get('pitanje41', '')
    odgovor_pitanje42 = session.get('pitanje42', '')
    odgovor_pitanje42_text = session.get('pitanje42_text', '')


    # Prikazivanje HTML template-a sa trenutnom stranicom upitnika
    trenutna_stranica = session.get('trenutna_stranica', 2)
    ukupan_broj_stranica = izracunaj_ukupan_broj_stranica()
    progres = izracunaj_napredak(trenutna_stranica, ukupan_broj_stranica)

    return render_template('tehnicka_pouzdanost_i_bezbednost.html', jedinstveni_id=jedinstveni_id, progres=progres,
        odgovor_pitanje14=odgovor_pitanje14,
        odgovor_pitanje15=odgovor_pitanje15,
        odgovor_pitanje15_text=odgovor_pitanje15_text,
        odgovor_pitanje16=odgovor_pitanje16,
        odgovor_pitanje16_text=odgovor_pitanje16_text,
        odgovor_pitanje17=odgovor_pitanje17,
        odgovor_pitanje17_text=odgovor_pitanje17_text,
        odgovor_pitanje18=odgovor_pitanje18,
        odgovor_pitanje18_text=odgovor_pitanje18_text,
        odgovor_pitanje19=odgovor_pitanje19,
        odgovor_pitanje19_text=odgovor_pitanje19_text,
        odgovor_pitanje20=odgovor_pitanje20,
        odgovor_pitanje20_text=odgovor_pitanje20_text,
        odgovor_pitanje21=odgovor_pitanje21,
        odgovor_pitanje22=odgovor_pitanje22,
        odgovor_pitanje22_text=odgovor_pitanje22_text,
        odgovor_pitanje23=odgovor_pitanje23,
        odgovor_pitanje24=odgovor_pitanje24,
        odgovor_pitanje24_text=odgovor_pitanje24_text,
        odgovor_pitanje25=odgovor_pitanje25,
        odgovor_pitanje25_text=odgovor_pitanje25_text,
        odgovor_pitanje26=odgovor_pitanje26,
        odgovor_pitanje26_text=odgovor_pitanje26_text,
        odgovor_pitanje27=odgovor_pitanje27,
        odgovor_pitanje27_text=odgovor_pitanje27_text,
        odgovor_pitanje28=odgovor_pitanje28,
        odgovor_pitanje29=odgovor_pitanje29,
        odgovor_pitanje29_text=odgovor_pitanje29_text,
        odgovor_pitanje30=odgovor_pitanje30,
        odgovor_pitanje30_text=odgovor_pitanje30_text,
        odgovor_pitanje31=odgovor_pitanje31,
        odgovor_pitanje31_text=odgovor_pitanje31_text,
        odgovor_pitanje32=odgovor_pitanje32,
        odgovor_pitanje32_text=odgovor_pitanje32_text,
        odgovor_pitanje33=odgovor_pitanje33,
        odgovor_pitanje33_text=odgovor_pitanje33_text,
        odgovor_pitanje34=odgovor_pitanje34,
        odgovor_pitanje34_text=odgovor_pitanje34_text,
        odgovor_pitanje35=odgovor_pitanje35,
        odgovor_pitanje35_text=odgovor_pitanje35_text,
        odgovor_pitanje36=odgovor_pitanje36,
        odgovor_pitanje36_text=odgovor_pitanje36_text,
        odgovor_pitanje37=odgovor_pitanje37,
        odgovor_pitanje37_text=odgovor_pitanje37_text,
        odgovor_pitanje38=odgovor_pitanje38,
        odgovor_pitanje38_text=odgovor_pitanje38_text,
        odgovor_pitanje39=odgovor_pitanje39,
        odgovor_pitanje40=odgovor_pitanje40,
        odgovor_pitanje40_text=odgovor_pitanje40_text,
        odgovor_pitanje41=odgovor_pitanje41,
        odgovor_pitanje42=odgovor_pitanje42,
        odgovor_pitanje42_text=odgovor_pitanje42_text
                           )


@app.route('/privatnost_zastita_podataka_i_upravljanje_podacima', methods=['GET', 'POST'])
def privatnost_zastita_podataka_i_upravljanje_podacima():
    # Provera da li korisnik ima jedinstveni ID u sessionu
    if 'jedinstveni_id' in request.cookies:
        # Ako postoji jedinstveni ID u sessionu, koristimo ga
        jedinstveni_id = request.cookies['jedinstveni_id']
    else:
        # Ako ne postoji jedinstveni ID u sessionu, korisnik nije pravilno započeo upitnik, preusmeravamo ga na početnu stranicu
        return redirect(url_for('index'))
  
    session['trenutna_stranica'] = 3

    if request.method == 'POST':
        # Provera akcije koju je korisnik izabrao (sledeća stranica ili prethodna stranica)
        action = request.form['action']

        if action == 'next':

            # Čuvanje odgovora na pitanja o privatnosti, zaštiti podataka i upravljanju podacima
            session['pitanje43'] = request.form.getlist('pitanje43')
            session['pitanje43_text'] = request.form.get('pitanje43_text_odgovor', '')
            session['pitanje44'] = request.form.get('pitanje44', '')
            session['pitanje44_text'] = request.form.get('pitanje44_text_odgovor', '')
            session['pitanje45'] = request.form.get('pitanje45', '')
            session['pitanje45_text'] = request.form.get('pitanje45_text_odgovor', '')
            session['pitanje46'] = request.form.getlist('pitanje46')
            session['pitanje46_text'] = request.form.get('pitanje46_text_odgovor', '')
            session['pitanje47'] = request.form.get('pitanje47', '')
            session['pitanje48'] = request.form.get('pitanje48', '')
            session['pitanje48_text'] = request.form.get('pitanje48_text_odgovor', '')
            session['pitanje49'] = request.form.get('pitanje49', '')
            session['pitanje49_text'] = request.form.get('pitanje49_text_odgovor', '')
            session['pitanje50'] = request.form.getlist('pitanje50')
            session['pitanje51'] = request.form.get('pitanje51', '')
            session['pitanje52'] = request.form.get('pitanje52', '')
            session['pitanje53'] = request.form.get('pitanje53', '')
            session['pitanje54'] = request.form.get('pitanje54', '')
            session['pitanje54_text'] = request.form.get('pitanje54_text_odgovor', '')
            
        # Slično postupamo i za ostala pitanja na stranici "Privatnost, zaštita podataka i upravljanje podacima"
            return redirect(url_for('privatnost_zastita_podataka_i_upravljanje_podacima_preporuke'))

    
        elif action == 'prev':
            # Ako je izabrana prethodna stranica, smanjujemo trenutnu stranicu za 1
            session['trenutna_stranica'] -= 1

            return redirect(url_for('tehnicka_pouzdanost_i_bezbednost'))

            # Možete ovde dodati logiku za čuvanje prethodnih odgovora u bazi podataka ili neki drugi način čuvanja
    
        else:
            # Ako korisnik šalje neku drugu akciju, preusmeravamo ga na početnu stranicu
            return redirect(url_for('index'))


    odgovor_pitanje43 = session.get('pitanje43', [])
    odgovor_pitanje43_text = session.get('pitanje43_text', '')
    odgovor_pitanje44 = session.get('pitanje44', '')
    odgovor_pitanje44_text = session.get('pitanje44_text', '')
    odgovor_pitanje45 = session.get('pitanje45', '')
    odgovor_pitanje45_text = session.get('pitanje45_text', '')
    odgovor_pitanje46 = session.get('pitanje46', [])
    odgovor_pitanje46_text = session.get('pitanje46_text', '')
    odgovor_pitanje47 = session.get('pitanje47', '')
    odgovor_pitanje48 = session.get('pitanje48', '')
    odgovor_pitanje48_text = session.get('pitanje48_text', '')
    odgovor_pitanje49 = session.get('pitanje49', '')
    odgovor_pitanje49_text = session.get('pitanje49_text', '')
    odgovor_pitanje50 = session.get('pitanje50', [])
    odgovor_pitanje51 = session.get('pitanje51', '')
    odgovor_pitanje52 = session.get('pitanje52', '')
    odgovor_pitanje53 = session.get('pitanje53', '')
    odgovor_pitanje54 = session.get('pitanje54', '')
    odgovor_pitanje54_text = session.get('pitanje54_text', '')

    trenutna_stranica = session.get('trenutna_stranica', 3)
    ukupan_broj_stranica = izracunaj_ukupan_broj_stranica()
    progres = izracunaj_napredak(trenutna_stranica, ukupan_broj_stranica)
   
    return render_template('privatnost_zastita_podataka_i_upravljanje_podacima.html', jedinstveni_id=jedinstveni_id, progres=progres,
                            odgovor_pitanje43=odgovor_pitanje43,
                            odgovor_pitanje43_text=odgovor_pitanje43_text,
                            odgovor_pitanje44=odgovor_pitanje44,
                            odgovor_pitanje44_text=odgovor_pitanje44_text,
                            odgovor_pitanje45=odgovor_pitanje45,
                            odgovor_pitanje45_text=odgovor_pitanje45_text,
                            odgovor_pitanje46=odgovor_pitanje46,
                            odgovor_pitanje46_text=odgovor_pitanje46_text,
                            odgovor_pitanje47=odgovor_pitanje47,
                            odgovor_pitanje48=odgovor_pitanje48,
                            odgovor_pitanje48_text=odgovor_pitanje48_text,
                            odgovor_pitanje49=odgovor_pitanje49,
                            odgovor_pitanje49_text=odgovor_pitanje49_text,
                            odgovor_pitanje50=odgovor_pitanje50,
                            odgovor_pitanje51=odgovor_pitanje51,
                            odgovor_pitanje52=odgovor_pitanje52,
                            odgovor_pitanje53=odgovor_pitanje53,
                            odgovor_pitanje54=odgovor_pitanje54,
                            odgovor_pitanje54_text=odgovor_pitanje54_text
                           )

@app.route('/transparentnost', methods=['GET', 'POST'])
def transparentnost():
    # Provera da li korisnik ima jedinstveni ID u sessionu
    if 'jedinstveni_id' in request.cookies:
        # Ako postoji jedinstveni ID u sessionu, koristimo ga
        jedinstveni_id = request.cookies['jedinstveni_id']
    else:
        # Ako ne postoji jedinstveni ID u sessionu, korisnik nije pravilno započeo upitnik, preusmeravamo ga na početnu stranicu
        return redirect(url_for('index'))
  
    session['trenutna_stranica'] = 4

    if request.method == 'POST':
            # Provera akcije koju je korisnik izabrao (sledeća stranica ili prethodna stranica)
        action = request.form['action']

        if action == 'next':
        # Čuvanje odgovora na pitanja o transparentnosti
            session['pitanje55'] = request.form.get('pitanje55', '')
            session['pitanje56'] = request.form.get('pitanje56', '')
            session['pitanje57'] = request.form.getlist('pitanje57')
            session['pitanje57_text'] = request.form.get('pitanje57_text_odgovor', '')
            session['pitanje58'] = request.form.get('pitanje58', '')
            session['pitanje59'] = request.form.get('pitanje59', '')
            session['pitanje60'] = request.form.getlist('pitanje60')
            session['pitanje60_text'] = request.form.get('pitanje60_text_odgovor', '')
            session['pitanje61'] = request.form.get('pitanje61', '')
            session['pitanje62'] = request.form.get('pitanje62', '')
            session['pitanje62_text'] = request.form.get('pitanje62_text_odgovor', '')
            session['pitanje63'] = request.form.get('pitanje63', '')
            session['pitanje64'] = request.form.get('pitanje64', '')
            session['pitanje64_text'] = request.form.get('pitanje64_text_odgovor', '')
            session['pitanje65'] = request.form.getlist('pitanje65')
            session['pitanje65_text'] = request.form.get('pitanje65_text_odgovor', '')
            session['pitanje66'] = request.form.get('pitanje66', '')
            session['pitanje66_text'] = request.form.get('pitanje66_text_odgovor', '')
            session['pitanje67'] = request.form.get('pitanje67', '')
            session['pitanje67_text'] = request.form.get('pitanje67_text_odgovor', '')
            session['pitanje68'] = request.form.get('pitanje68', '')
            session['pitanje69'] = request.form.get('pitanje69', '')
            session['pitanje69_text'] = request.form.get('pitanje69_text_odgovor', '')
            session['pitanje70'] = request.form.get('pitanje70', '')
            session['pitanje70_text'] = request.form.get('pitanje70_text_odgovor', '')
            session['pitanje71'] = request.form.get('pitanje71', '')
            session['pitanje71_text'] = request.form.get('pitanje71_text_odgovor', '')
            session['pitanje72'] = request.form.get('pitanje72', '')
            session['pitanje73'] = request.form.get('pitanje73', '')
            
        # Slično postupamo i za ostala pitanja na stranici "Transparentnost"

        # Nakon što sačuvamo sve odgovore, preusmeravamo korisnika na sledeću stranicu upitnika
            return redirect(url_for('transparentnost_preporuke'))
    
        elif action == 'prev':
            # Ako je izabrana prethodna stranica, smanjujemo trenutnu stranicu za 1
            session['trenutna_stranica'] -= 1

            return redirect(url_for('privatnost_zastita_podataka_i_upravljanje_podacima'))

            # Možete ovde dodati logiku za čuvanje prethodnih odgovora u bazi podataka ili neki drugi način čuvanja
    
        else:
            # Ako korisnik šalje neku drugu akciju, preusmeravamo ga na početnu stranicu
            return redirect(url_for('index'))

    
    odgovor_pitanje55 = session.get('pitanje55', '')
    odgovor_pitanje56 = session.get('pitanje56', '')
    odgovor_pitanje57 = session.get('pitanje57', [])
    odgovor_pitanje57_text = session.get('pitanje57_text', '')
    odgovor_pitanje58 = session.get('pitanje58', '')
    odgovor_pitanje59 = session.get('pitanje59', '')
    odgovor_pitanje60 = session.get('pitanje60', [])
    odgovor_pitanje60_text = session.get('pitanje60_text', '')
    odgovor_pitanje61 = session.get('pitanje61', '')
    odgovor_pitanje62 = session.get('pitanje62', '')
    odgovor_pitanje62_text = session.get('pitanje62_text', '')
    odgovor_pitanje63 = session.get('pitanje63', '')
    odgovor_pitanje64 = session.get('pitanje64', '')
    odgovor_pitanje64_text = session.get('pitanje64_text', '')
    odgovor_pitanje65 = session.get('pitanje65', [])
    odgovor_pitanje65_text = session.get('pitanje65_text', '')
    odgovor_pitanje66 = session.get('pitanje66', '')
    odgovor_pitanje66_text = session.get('pitanje66_text', '')
    odgovor_pitanje67 = session.get('pitanje67', '')
    odgovor_pitanje67_text = session.get('pitanje67_text', '')
    odgovor_pitanje68 = session.get('pitanje68', '')
    odgovor_pitanje69 = session.get('pitanje69', '')
    odgovor_pitanje69_text = session.get('pitanje69_text', '')
    odgovor_pitanje70 = session.get('pitanje70', '')
    odgovor_pitanje70_text = session.get('pitanje70_text', '')
    odgovor_pitanje71 = session.get('pitanje71', '')
    odgovor_pitanje71_text = session.get('pitanje71_text', '')
    odgovor_pitanje72 = session.get('pitanje72', '')
    odgovor_pitanje73 = session.get('pitanje73', '')

    trenutna_stranica = session.get('trenutna_stranica', 4)
    ukupan_broj_stranica = izracunaj_ukupan_broj_stranica()
    progres = izracunaj_napredak(trenutna_stranica, ukupan_broj_stranica)
    
    return render_template('transparentnost.html', jedinstveni_id=jedinstveni_id, progres=progres,
                            odgovor_pitanje55=odgovor_pitanje55,
                            odgovor_pitanje56=odgovor_pitanje56,
                            odgovor_pitanje57=odgovor_pitanje57,
                            odgovor_pitanje57_text=odgovor_pitanje57_text,
                            odgovor_pitanje58=odgovor_pitanje58,
                            odgovor_pitanje59=odgovor_pitanje59,
                            odgovor_pitanje60=odgovor_pitanje60,
                            odgovor_pitanje60_text=odgovor_pitanje60_text,
                            odgovor_pitanje61=odgovor_pitanje61,
                            odgovor_pitanje62=odgovor_pitanje62,
                            odgovor_pitanje62_text=odgovor_pitanje62_text,
                            odgovor_pitanje63=odgovor_pitanje63,
                            odgovor_pitanje64=odgovor_pitanje64,
                            odgovor_pitanje64_text=odgovor_pitanje64_text,
                            odgovor_pitanje65=odgovor_pitanje65,
                            odgovor_pitanje65_text=odgovor_pitanje65_text,
                            odgovor_pitanje66=odgovor_pitanje66,
                            odgovor_pitanje66_text=odgovor_pitanje66_text,
                            odgovor_pitanje67=odgovor_pitanje67,
                            odgovor_pitanje67_text=odgovor_pitanje67_text,
                            odgovor_pitanje68=odgovor_pitanje68,
                            odgovor_pitanje69=odgovor_pitanje69,
                            odgovor_pitanje69_text=odgovor_pitanje69_text,
                            odgovor_pitanje70=odgovor_pitanje70,
                            odgovor_pitanje70_text=odgovor_pitanje70_text,
                            odgovor_pitanje71=odgovor_pitanje71,
                            odgovor_pitanje71_text=odgovor_pitanje71_text,
                            odgovor_pitanje72=odgovor_pitanje72,
                            odgovor_pitanje73=odgovor_pitanje73
                            
                           )

# Implementacija ruta i funkcionalnosti za stranice:
# "razlicitost_nediskriminacija_i_ravnopravnost", "društveno_i_ekonomsko_blagostanje" i "odgovornost" ...

@app.route('/razlicitost_nediskriminacija_i_ravnopravnost', methods=['GET', 'POST'])
def razlicitost_nediskriminacija_i_ravnopravnost():
    # Provera da li korisnik ima jedinstveni ID u sesiji
    if 'jedinstveni_id' in request.cookies:
        # Ako postoji jedinstveni ID u sesiji, koristimo ga
        jedinstveni_id = request.cookies['jedinstveni_id']
    else:
        # Ako ne postoji jedinstveni ID u sesiji, korisnik nije pravilno započeo upitnik, preusmeravamo ga na početnu stranicu
        return redirect(url_for('index'))

    session['trenutna_stranica'] = 5

    if request.method == 'POST':
            # Provera akcije koju je korisnik izabrao (sledeća stranica ili prethodna stranica)
        action = request.form['action']

        if action == 'next':
        # Čuvanje odgovora na pitanja o različitosti, nediskriminaciji i ravnopravnosti
            session['pitanje74'] = request.form.get('pitanje74', '')
            session['pitanje75'] = request.form.get('pitanje75', '')
            session['pitanje75_text'] = request.form.get('pitanje75_text_odgovor', '')
            session['pitanje76'] = request.form.get('pitanje76', '')
            session['pitanje77'] = request.form.get('pitanje77', '')
            session['pitanje78'] = request.form.get('pitanje78', '')
            session['pitanje79'] = request.form.get('pitanje79', '')
            session['pitanje80'] = request.form.get('pitanje80', '')
            session['pitanje81'] = request.form.get('pitanje81', '')
            session['pitanje82'] = request.form.get('pitanje82', '')
            session['pitanje82_text'] = request.form.get('pitanje82_text_odgovor', '')
            session['pitanje83'] = request.form.get('pitanje83', '')
            session['pitanje83_text'] = request.form.get('pitanje83_text_odgovor', '')
            session['pitanje84'] = request.form.get('pitanje84', '')
            session['pitanje84_text'] = request.form.get('pitanje84_text_odgovor', '')
            session['pitanje85'] = request.form.get('pitanje85', '')
            session['pitanje86'] = request.form.get('pitanje86', '')
            session['pitanje86_text'] = request.form.get('pitanje86_text_odgovor', '')
            
        # Slično postupamo i za ostala pitanja na stranici "Različitost, nediskriminacija i ravnopravnost"

        # Nakon što sačuvamo sve odgovore, preusmeravamo korisnika na sledeću stranicu upitnika
            return redirect(url_for('razlicitost_nediskriminacija_i_ravnopravnost_preporuke'))

        elif action == 'prev':
            # Ako je izabrana prethodna stranica, smanjujemo trenutnu stranicu za 1
            session['trenutna_stranica'] -= 1

            return redirect(url_for('transparentnost'))

            # Možete ovde dodati logiku za čuvanje prethodnih odgovora u bazi podataka ili neki drugi način čuvanja
    
        else:
            # Ako korisnik šalje neku drugu akciju, preusmeravamo ga na početnu stranicu
            return redirect(url_for('index'))

    odgovor_pitanje74 = session.get('pitanje74', '')
    odgovor_pitanje75 = session.get('pitanje75', '')
    odgovor_pitanje75_text = session.get('pitanje75_text', '')
    odgovor_pitanje76 = session.get('pitanje76', '')
    odgovor_pitanje77 = session.get('pitanje77', '')
    odgovor_pitanje78 = session.get('pitanje78', '')
    odgovor_pitanje79 = session.get('pitanje79', '')
    odgovor_pitanje80 = session.get('pitanje80', '')
    odgovor_pitanje81 = session.get('pitanje81', '')
    odgovor_pitanje82 = session.get('pitanje82', '')
    odgovor_pitanje82_text = session.get('pitanje82_text', '')
    odgovor_pitanje83 = session.get('pitanje83', '')
    odgovor_pitanje83_text = session.get('pitanje83_text', '')
    odgovor_pitanje84 = session.get('pitanje84', '')
    odgovor_pitanje84_text = session.get('pitanje84_text', '')
    odgovor_pitanje85 = session.get('pitanje85', '')
    odgovor_pitanje86 = session.get('pitanje86', '')
    odgovor_pitanje86_text = session.get('pitanje86_text', '')


    trenutna_stranica = session.get('trenutna_stranica', 5)
    ukupan_broj_stranica = izracunaj_ukupan_broj_stranica()
    progres = izracunaj_napredak(trenutna_stranica, ukupan_broj_stranica)

    return render_template('razlicitost_nediskriminacija_i_ravnopravnost.html', jedinstveni_id=jedinstveni_id, progres=progres,
                            odgovor_pitanje74=odgovor_pitanje74,
                            odgovor_pitanje75=odgovor_pitanje75,
                            odgovor_pitanje75_text=odgovor_pitanje75_text,
                            odgovor_pitanje76=odgovor_pitanje76,
                            odgovor_pitanje77=odgovor_pitanje77,
                            odgovor_pitanje78=odgovor_pitanje78,
                            odgovor_pitanje79=odgovor_pitanje79,
                            odgovor_pitanje80=odgovor_pitanje80,
                            odgovor_pitanje81=odgovor_pitanje81,
                            odgovor_pitanje82=odgovor_pitanje82,
                            odgovor_pitanje82_text=odgovor_pitanje82_text,
                            odgovor_pitanje83=odgovor_pitanje83,
                            odgovor_pitanje83_text=odgovor_pitanje83_text,
                            odgovor_pitanje84=odgovor_pitanje84,
                            odgovor_pitanje84_text=odgovor_pitanje84_text,
                            odgovor_pitanje85=odgovor_pitanje85,
                            odgovor_pitanje86=odgovor_pitanje86,
                            odgovor_pitanje86_text=odgovor_pitanje86_text
                          
                           )

@app.route('/drustveno_i_ekonomsko_blagostanje', methods=['GET', 'POST'])
def drustveno_i_ekonomsko_blagostanje():
    # Provera da li korisnik ima jedinstveni ID u sessionu
    if 'jedinstveni_id' in request.cookies:
        # Ako postoji jedinstveni ID u sessionu, koristimo ga
        jedinstveni_id = request.cookies['jedinstveni_id']
    else:
        # Ako ne postoji jedinstveni ID u sessionu, korisnik nije pravilno započeo upitnik, preusmeravamo ga na početnu stranicu
        return redirect(url_for('index'))
  
    session['trenutna_stranica'] = 6

    if request.method == 'POST':
            # Provera akcije koju je korisnik izabrao (sledeća stranica ili prethodna stranica)
        action = request.form['action']

        if action == 'next':
        # Čuvanje odgovora na pitanja o društvenom i ekonomskom blagostanju
            session['pitanje87'] = request.form.get('pitanje87', '')
            session['pitanje87_text'] = request.form.get('pitanje87_text_odgovor', '')
            session['pitanje88'] = request.form.get('pitanje88', '')
            session['pitanje88_text'] = request.form.get('pitanje88_text_odgovor', '')
            session['pitanje89'] = request.form.get('pitanje89', '')
            session['pitanje89_text'] = request.form.get('pitanje89_text_odgovor', '')
            session['pitanje90'] = request.form.get('pitanje90', '')
            session['pitanje91'] = request.form.get('pitanje91', '')
            session['pitanje92'] = request.form.get('pitanje92', '')
            session['pitanje92_text'] = request.form.get('pitanje92_text_odgovor', '')
            session['pitanje93'] = request.form.get('pitanje93', '')
            session['pitanje94'] = request.form.get('pitanje94', '')
            session['pitanje94_text'] = request.form.get('pitanje94_text_odgovor', '')
            session['pitanje95'] = request.form.get('pitanje95', '')
            session['pitanje96'] = request.form.get('pitanje96', '')
            session['pitanje97'] = request.form.get('pitanje97', '')
            session['pitanje98'] = request.form.get('pitanje98', '')
            session['pitanje99'] = request.form.get('pitanje99', '')
            session['pitanje100'] = request.form.get('pitanje100', '')
            session['pitanje100_text'] = request.form.get('pitanje100_text_odgovor', '')
            session['pitanje101'] = request.form.get('pitanje101', '')
            session['pitanje101_text'] = request.form.get('pitanje101_text_odgovor', '')
            
        
        # Slično postupamo i za ostala pitanja na stranici "Društveno i ekonomsko blagostanje"

        # Nakon što sačuvamo sve odgovore, preusmeravamo korisnika na sledeću stranicu upitnika
            return redirect(url_for('drustveno_i_ekonomsko_blagostanje_preporuke'))

        elif action == 'prev':
            # Ako je izabrana prethodna stranica, smanjujemo trenutnu stranicu za 1
            session['trenutna_stranica'] -= 1

            return redirect(url_for('razlicitost_nediskriminacija_i_ravnopravnost'))

            # Možete ovde dodati logiku za čuvanje prethodnih odgovora u bazi podataka ili neki drugi način čuvanja
    
        else:
            # Ako korisnik šalje neku drugu akciju, preusmeravamo ga na početnu stranicu
            return redirect(url_for('index'))


    odgovor_pitanje87 = session.get('pitanje87', '')
    odgovor_pitanje87_text = session.get('pitanje87_text', '')
    odgovor_pitanje88 = session.get('pitanje88', '')
    odgovor_pitanje88_text = session.get('pitanje88_text', '')
    odgovor_pitanje89 = session.get('pitanje89', '')
    odgovor_pitanje89_text = session.get('pitanje89_text', '')
    odgovor_pitanje90 = session.get('pitanje90', '')
    odgovor_pitanje91 = session.get('pitanje91', '')
    odgovor_pitanje92 = session.get('pitanje92', '')
    odgovor_pitanje92_text = session.get('pitanje92_text', '')
    odgovor_pitanje93 = session.get('pitanje93', '')
    odgovor_pitanje94 = session.get('pitanje94', '')
    odgovor_pitanje94_text = session.get('pitanje94_text', '')
    odgovor_pitanje95 = session.get('pitanje95', '')
    odgovor_pitanje96 = session.get('pitanje96', '')
    odgovor_pitanje97 = session.get('pitanje97', '')
    odgovor_pitanje98 = session.get('pitanje98', '')
    odgovor_pitanje99 = session.get('pitanje99', '')
    odgovor_pitanje100 = session.get('pitanje100', '')
    odgovor_pitanje100_text = session.get('pitanje100_text', '')
    odgovor_pitanje101 = session.get('pitanje101', '')
    odgovor_pitanje101_text = session.get('pitanje101_text', '')

    trenutna_stranica = session.get('trenutna_stranica', 6)
    ukupan_broj_stranica = izracunaj_ukupan_broj_stranica()
    progres = izracunaj_napredak(trenutna_stranica, ukupan_broj_stranica)

    return render_template('drustveno_i_ekonomsko_blagostanje.html', jedinstveni_id=jedinstveni_id, progres=progres,
                            odgovor_pitanje87=odgovor_pitanje87,
                            odgovor_pitanje87_text=odgovor_pitanje87_text,
                            odgovor_pitanje88=odgovor_pitanje88,
                            odgovor_pitanje88_text=odgovor_pitanje88_text,
                            odgovor_pitanje89=odgovor_pitanje89,
                            odgovor_pitanje89_text=odgovor_pitanje89_text,
                            odgovor_pitanje90=odgovor_pitanje90,
                            odgovor_pitanje91=odgovor_pitanje91,
                            odgovor_pitanje92=odgovor_pitanje92,
                            odgovor_pitanje92_text=odgovor_pitanje92_text,
                            odgovor_pitanje93=odgovor_pitanje93,
                            odgovor_pitanje94=odgovor_pitanje94,
                            odgovor_pitanje94_text=odgovor_pitanje94_text,
                            odgovor_pitanje95=odgovor_pitanje95,
                            odgovor_pitanje96=odgovor_pitanje96,
                            odgovor_pitanje97=odgovor_pitanje97,
                            odgovor_pitanje98=odgovor_pitanje98,
                            odgovor_pitanje99=odgovor_pitanje99,
                            odgovor_pitanje100=odgovor_pitanje100,
                            odgovor_pitanje100_text=odgovor_pitanje100_text,
                            odgovor_pitanje101=odgovor_pitanje101,
                            odgovor_pitanje101_text=odgovor_pitanje101_text
                           )

@app.route('/odgovornost', methods=['GET', 'POST'])
def odgovornost():
    # Provera da li korisnik ima jedinstveni ID u sessionu
    if 'jedinstveni_id' in request.cookies:
        # Ako postoji jedinstveni ID u sessionu, koristimo ga
        jedinstveni_id = request.cookies['jedinstveni_id']
    else:
        # Ako ne postoji jedinstveni ID u sessionu, korisnik nije pravilno započeo upitnik, preusmeravamo ga na početnu stranicu
        return redirect(url_for('index'))
  
    session['trenutna_stranica'] = 7

    if request.method == 'POST':
            # Provera akcije koju je korisnik izabrao (sledeća stranica ili prethodna stranica)
        action = request.form['action']

        if action == 'next':
        # Čuvanje odgovora na pitanja o društvenom i ekonomskom blagostanju
        
            session['pitanje102'] = request.form.get('pitanje102', '')
            session['pitanje103'] = request.form.get('pitanje103', '')
            session['pitanje104'] = request.form.get('pitanje104', '')
            session['pitanje104_text'] = request.form.get('pitanje104_text_odgovor', '')
            session['pitanje105'] = request.form.get('pitanje105', '')
            session['pitanje105_text'] = request.form.get('pitanje105_text_odgovor', '')
            session['pitanje106'] = request.form.get('pitanje106', '')
            session['pitanje106_text'] = request.form.get('pitanje106_text_odgovor', '')
            session['pitanje107'] = request.form.get('pitanje107', '')
            session['pitanje108'] = request.form.get('pitanje108', '')
            session['pitanje109'] = request.form.get('pitanje109', '')
            session['pitanje110'] = request.form.get('pitanje110', '')
            session['pitanje111'] = request.form.get('pitanje111', '')
            session['pitanje112'] = request.form.get('pitanje112', '')
            
        # Postavite trenutnu stranicu na 8 kako biste označili da je korisnik završio upitnik
            session['trenutna_stranica'] = 8

        # Preusmerite korisnika na stranicu "kraj_upitnika"
            return redirect(url_for('odgovornost_preporuke'))
                # Možete ovde dodati logiku za čuvanje prethodnih odgovora u bazi podataka ili neki drugi način čuvanja

        elif action == 'prev':
            # Ako je izabrana prethodna stranica, smanjujemo trenutnu stranicu za 1
            session['trenutna_stranica'] -= 1

            return redirect(url_for('drustveno_i_ekonomsko_blagostanje'))

            # Možete ovde dodati logiku za čuvanje prethodnih odgovora u bazi podataka ili neki drugi način čuvanja
    
        else:
            # Ako korisnik šalje neku drugu akciju, preusmeravamo ga na početnu stranicu
            return redirect(url_for('index'))


    odgovor_pitanje102 = session.get('pitanje102', '')
    odgovor_pitanje103 = session.get('pitanje103', '')
    odgovor_pitanje104 = session.get('pitanje104', '')
    odgovor_pitanje104_text = session.get('pitanje104_text', '')
    odgovor_pitanje105 = session.get('pitanje105', '')
    odgovor_pitanje105_text = session.get('pitanje105_text', '')
    odgovor_pitanje106 = session.get('pitanje106', '')
    odgovor_pitanje106_text = session.get('pitanje106_text', '')
    odgovor_pitanje107 = session.get('pitanje107', '')
    odgovor_pitanje108 = session.get('pitanje108', '')
    odgovor_pitanje109 = session.get('pitanje109', '')
    odgovor_pitanje110 = session.get('pitanje110', '')
    odgovor_pitanje111 = session.get('pitanje111', '')
    odgovor_pitanje112 = session.get('pitanje112', '')
    
    trenutna_stranica = session.get('trenutna_stranica', 7)
    ukupan_broj_stranica = izracunaj_ukupan_broj_stranica()
    progres = izracunaj_napredak(trenutna_stranica, ukupan_broj_stranica)

    return render_template('odgovornost.html', jedinstveni_id=jedinstveni_id, progres=progres,
                            odgovor_pitanje102=odgovor_pitanje102,
                            odgovor_pitanje103=odgovor_pitanje103,
                            odgovor_pitanje104=odgovor_pitanje104,
                            odgovor_pitanje104_text=odgovor_pitanje104_text,
                            odgovor_pitanje105=odgovor_pitanje105,
                            odgovor_pitanje105_text=odgovor_pitanje105_text,
                            odgovor_pitanje106=odgovor_pitanje106,
                            odgovor_pitanje106_text=odgovor_pitanje106_text,
                            odgovor_pitanje107=odgovor_pitanje107,
                            odgovor_pitanje108=odgovor_pitanje108,
                            odgovor_pitanje109=odgovor_pitanje109,
                            odgovor_pitanje110=odgovor_pitanje110,
                            odgovor_pitanje111=odgovor_pitanje111,
                            odgovor_pitanje112=odgovor_pitanje112
                        
                           )


@app.route('/delovanje_i_kontrola_preporuke')
def delovanje_i_kontrola_preporuke():
    # Ovde možete dodati logiku za prikazivanje preporuka
    return render_template('delovanje_i_kontrola_preporuke.html')

@app.route('/tehnicka_pouzdanost_i_bezbednost_preporuke')
def tehnicka_pouzdanost_i_bezbednost_preporuke():
    # Ovde možete dodati logiku za prikazivanje preporuka
    return render_template('tehnicka_pouzdanost_i_bezbednost_preporuke.html')

@app.route('/privatnost_zastita_podataka_i_upravljanje_podacima_preporuke')
def privatnost_zastita_podataka_i_upravljanje_podacima_preporuke():
    # Ovde možete dodati logiku za prikazivanje preporuka
    return render_template('privatnost_zastita_podataka_i_upravljanje_podacima_preporuke.html')

@app.route('/transparentnost_preporuke')
def transparentnost_preporuke():
    # Ovde možete dodati logiku za prikazivanje preporuka
    return render_template('transparentnost_preporuke.html')

@app.route('/razlicitost_nediskriminacija_i_ravnopravnost_preporuke')
def razlicitost_nediskriminacija_i_ravnopravnost_preporuke():
    # Ovde možete dodati logiku za prikazivanje preporuka
    return render_template('razlicitost_nediskriminacija_i_ravnopravnost_preporuke.html')

@app.route('/drustveno_i_ekonomsko_blagostanje_preporuke')
def drustveno_i_ekonomsko_blagostanje_preporuke():
    # Ovde možete dodati logiku za prikazivanje preporuka
    return render_template('drustveno_i_ekonomsko_blagostanje_preporuke.html')

@app.route('/odgovornost_preporuke')
def odgovornost_preporuke():
    # Ovde možete dodati logiku za prikazivanje preporuka
    return render_template('odgovornost_preporuke.html')


@app.route('/kraj_upitnika')
def kraj_upitnika():
    # Provera da li korisnik ima jedinstveni ID u sesiji
    if 'jedinstveni_id' in request.cookies:
        # Ako postoji jedinstveni ID u sesiji, koristimo ga
        jedinstveni_id = request.cookies['jedinstveni_id']
    else:
        # Ako ne postoji jedinstveni ID u sesiji, korisnik nije pravilno započeo upitnik, preusmeravamo ga na početnu stranicu
        return redirect(url_for('index'))

    # Dohvati odgovore korisnika iz baze podataka
    odgovori_korisnika = dohvati_odgovore_korisnika(jedinstveni_id)

    # Dohvatanje odgovora iz sesije
    
    odgovor_pitanje1 = session.get('pitanje1', '')
    odgovor_pitanje2 = session.get('pitanje2', '')
    odgovor_pitanje2_text = session.get('pitanje2_text', '')
    odgovor_pitanje3 = session.get('pitanje3', '')
    odgovor_pitanje3_text = session.get('pitanje3_text', '')
    odgovor_pitanje4 = session.get('pitanje4', '')
    odgovor_pitanje5 = session.get('pitanje5', '')
    odgovor_pitanje5_text = session.get('pitanje5_text', '')
    odgovor_pitanje6 = session.get('pitanje6', '')
    odgovor_pitanje6_text = session.get('pitanje6_text', '')
    odgovor_pitanje7 = session.get('pitanje7', '')
    odgovor_pitanje7_text = session.get('pitanje7_text', '')
    odgovor_pitanje8 = session.get('pitanje8', '')
    odgovor_pitanje8_text = session.get('pitanje8_text', '')
    odgovor_pitanje9 = session.get('pitanje9', '')
    odgovor_pitanje10 = session.get('pitanje10', '')
    odgovor_pitanje11 = session.get('pitanje11', '')
    odgovor_pitanje11_text = session.get('pitanje11_text', '')
    odgovor_pitanje12 = session.get('pitanje12', '')
    odgovor_pitanje12_text = session.get('pitanje12_text', '')
    odgovor_pitanje13 = session.get('pitanje13', '')
    odgovor_pitanje13_text = session.get('pitanje13_text', '')
    odgovor_pitanje14 = session.get('pitanje14', '')
    odgovor_pitanje15 = session.get('pitanje15', '')
    odgovor_pitanje15_text = session.get('pitanje15_text', '')
    odgovor_pitanje16 = session.get('pitanje16', '')
    odgovor_pitanje16_text = session.get('pitanje16_text', '')
    odgovor_pitanje17 = session.get('pitanje17', '')
    odgovor_pitanje17_text = session.get('pitanje17_text', '')
    odgovor_pitanje18 = session.get('pitanje18', [])
    odgovor_pitanje18_text = session.get('pitanje18_text', '')
    odgovor_pitanje19 = session.get('pitanje19', '')
    odgovor_pitanje19_text = session.get('pitanje19_text', '')
    odgovor_pitanje20 = session.get('pitanje20', '')
    odgovor_pitanje20_text = session.get('pitanje20_text', '')
    odgovor_pitanje21 = session.get('pitanje21', '')
    odgovor_pitanje22 = session.get('pitanje22', '')
    odgovor_pitanje22_text = session.get('pitanje22_text', '')
    odgovor_pitanje23 = session.get('pitanje23', '')
    odgovor_pitanje24 = session.get('pitanje24', '')
    odgovor_pitanje24_text = session.get('pitanje24_text', '')
    odgovor_pitanje25 = session.get('pitanje25', '')
    odgovor_pitanje25_text = session.get('pitanje25_text', '')
    odgovor_pitanje26 = session.get('pitanje26', '')
    odgovor_pitanje26_text = session.get('pitanje26_text', '')
    odgovor_pitanje27 = session.get('pitanje27', '')
    odgovor_pitanje27_text = session.get('pitanje27_text', '')
    odgovor_pitanje28 = session.get('pitanje28', '')
    odgovor_pitanje29 = session.get('pitanje29', '')
    odgovor_pitanje29_text = session.get('pitanje29_text', '')
    odgovor_pitanje30 = session.get('pitanje30', '')
    odgovor_pitanje30_text = session.get('pitanje30_text', '')
    odgovor_pitanje31 = session.get('pitanje31', '')
    odgovor_pitanje31_text = session.get('pitanje31_text', '')
    odgovor_pitanje32 = session.get('pitanje32', '')
    odgovor_pitanje32_text = session.get('pitanje32_text', '')
    odgovor_pitanje33 = session.get('pitanje33', '')
    odgovor_pitanje33_text = session.get('pitanje33_text', '')
    odgovor_pitanje34 = session.get('pitanje34', '')
    odgovor_pitanje34_text = session.get('pitanje34_text', '')
    odgovor_pitanje35 = session.get('pitanje35', '')
    odgovor_pitanje35_text = session.get('pitanje35_text', '')
    odgovor_pitanje36 = session.get('pitanje36', '')
    odgovor_pitanje36_text = session.get('pitanje36_text', '')
    odgovor_pitanje37 = session.get('pitanje37', '')
    odgovor_pitanje37_text = session.get('pitanje37_text', '')
    odgovor_pitanje38 = session.get('pitanje38', '')
    odgovor_pitanje38_text = session.get('pitanje38_text', '')
    odgovor_pitanje39 = session.get('pitanje39', '')
    odgovor_pitanje40 = session.get('pitanje40', '')
    odgovor_pitanje40_text = session.get('pitanje40_text', '')
    odgovor_pitanje41 = session.get('pitanje41', '')
    odgovor_pitanje42 = session.get('pitanje42', '')
    odgovor_pitanje42_text = session.get('pitanje42_text', '')
    odgovor_pitanje43 = session.get('pitanje43', [])
    odgovor_pitanje43_text = session.get('pitanje43_text', '')
    odgovor_pitanje44 = session.get('pitanje44', '')
    odgovor_pitanje44_text = session.get('pitanje44_text', '')
    odgovor_pitanje45 = session.get('pitanje45', '')
    odgovor_pitanje45_text = session.get('pitanje45_text', '')
    odgovor_pitanje46 = session.get('pitanje46', [])
    odgovor_pitanje46_text = session.get('pitanje46_text', '')
    odgovor_pitanje47 = session.get('pitanje47', '')
    odgovor_pitanje48 = session.get('pitanje48', '')
    odgovor_pitanje48_text = session.get('pitanje48_text', '')
    odgovor_pitanje49 = session.get('pitanje49', '')
    odgovor_pitanje49_text = session.get('pitanje49_text', '')
    odgovor_pitanje50 = session.get('pitanje50', [])
    odgovor_pitanje51 = session.get('pitanje51', '')
    odgovor_pitanje52 = session.get('pitanje52', '')
    odgovor_pitanje53 = session.get('pitanje53', '')
    odgovor_pitanje54 = session.get('pitanje54', '')
    odgovor_pitanje54_text = session.get('pitanje54_text', '')
    odgovor_pitanje55 = session.get('pitanje55', '')
    odgovor_pitanje56 = session.get('pitanje56', '')
    odgovor_pitanje57 = session.get('pitanje57', [])
    odgovor_pitanje57_text = session.get('pitanje57_text', '')
    odgovor_pitanje58 = session.get('pitanje58', '')
    odgovor_pitanje59 = session.get('pitanje59', '')
    odgovor_pitanje60 = session.get('pitanje60', [])
    odgovor_pitanje60_text = session.get('pitanje60_text', '')
    odgovor_pitanje61 = session.get('pitanje61', '')
    odgovor_pitanje62 = session.get('pitanje62', '')
    odgovor_pitanje62_text = session.get('pitanje62_text', '')
    odgovor_pitanje63 = session.get('pitanje63', '')
    odgovor_pitanje64 = session.get('pitanje64', '')
    odgovor_pitanje64_text = session.get('pitanje64_text', '')
    odgovor_pitanje65 = session.get('pitanje65', [])
    odgovor_pitanje65_text = session.get('pitanje65_text', '')
    odgovor_pitanje66 = session.get('pitanje66', '')
    odgovor_pitanje66_text = session.get('pitanje66_text', '')
    odgovor_pitanje67 = session.get('pitanje67', '')
    odgovor_pitanje67_text = session.get('pitanje67_text', '')
    odgovor_pitanje68 = session.get('pitanje68', '')
    odgovor_pitanje69 = session.get('pitanje69', '')
    odgovor_pitanje69_text = session.get('pitanje69_text', '')
    odgovor_pitanje70 = session.get('pitanje70', '')
    odgovor_pitanje70_text = session.get('pitanje70_text', '')
    odgovor_pitanje71 = session.get('pitanje71', '')
    odgovor_pitanje71_text = session.get('pitanje71_text', '')
    odgovor_pitanje72 = session.get('pitanje72', '')
    odgovor_pitanje73 = session.get('pitanje73', '')
    odgovor_pitanje74 = session.get('pitanje74', '')
    odgovor_pitanje75 = session.get('pitanje75', '')
    odgovor_pitanje75_text = session.get('pitanje75_text', '')
    odgovor_pitanje76 = session.get('pitanje76', '')
    odgovor_pitanje77 = session.get('pitanje77', '')
    odgovor_pitanje78 = session.get('pitanje78', '')
    odgovor_pitanje79 = session.get('pitanje79', '')
    odgovor_pitanje80 = session.get('pitanje80', '')
    odgovor_pitanje81 = session.get('pitanje81', '')
    odgovor_pitanje82 = session.get('pitanje82', '')
    odgovor_pitanje82_text = session.get('pitanje82_text', '')
    odgovor_pitanje83 = session.get('pitanje83', '')
    odgovor_pitanje83_text = session.get('pitanje83_text', '')
    odgovor_pitanje84 = session.get('pitanje84', '')
    odgovor_pitanje84_text = session.get('pitanje84_text', '')
    odgovor_pitanje85 = session.get('pitanje85', '')
    odgovor_pitanje86 = session.get('pitanje86', '')
    odgovor_pitanje86_text = session.get('pitanje86_text', '')
    odgovor_pitanje87 = session.get('pitanje87', '')
    odgovor_pitanje87_text = session.get('pitanje87_text', '')
    odgovor_pitanje88 = session.get('pitanje88', '')
    odgovor_pitanje88_text = session.get('pitanje88_text', '')
    odgovor_pitanje89 = session.get('pitanje89', '')
    odgovor_pitanje89_text = session.get('pitanje89_text', '')
    odgovor_pitanje90 = session.get('pitanje90', '')
    odgovor_pitanje91 = session.get('pitanje91', '')
    odgovor_pitanje92 = session.get('pitanje92', '')
    odgovor_pitanje92_text = session.get('pitanje92_text', '')
    odgovor_pitanje93 = session.get('pitanje93', '')
    odgovor_pitanje94 = session.get('pitanje94', '')
    odgovor_pitanje94_text = session.get('pitanje94_text', '')
    odgovor_pitanje95 = session.get('pitanje95', '')
    odgovor_pitanje96 = session.get('pitanje96', '')
    odgovor_pitanje97 = session.get('pitanje97', '')
    odgovor_pitanje98 = session.get('pitanje98', '')
    odgovor_pitanje99 = session.get('pitanje99', '')
    odgovor_pitanje100 = session.get('pitanje100', '')
    odgovor_pitanje100_text = session.get('pitanje100_text', '')
    odgovor_pitanje101 = session.get('pitanje101', '')
    odgovor_pitanje101_text = session.get('pitanje101_text', '')
    odgovor_pitanje102 = session.get('pitanje102', '')
    odgovor_pitanje103 = session.get('pitanje103', '')
    odgovor_pitanje104 = session.get('pitanje104', '')
    odgovor_pitanje104_text = session.get('pitanje104_text', '')
    odgovor_pitanje105 = session.get('pitanje105', '')
    odgovor_pitanje105_text = session.get('pitanje105_text', '')
    odgovor_pitanje106 = session.get('pitanje106', '')
    odgovor_pitanje106_text = session.get('pitanje106_text', '')
    odgovor_pitanje107 = session.get('pitanje107', '')
    odgovor_pitanje108 = session.get('pitanje108', '')
    odgovor_pitanje109 = session.get('pitanje109', '')
    odgovor_pitanje110 = session.get('pitanje110', '')
    odgovor_pitanje111 = session.get('pitanje111', '')
    odgovor_pitanje112 = session.get('pitanje112', '')


    vreme = datetime.now().strftime('%d.%m.%Y. %H:%M:%S')
    print(vreme)
   
    return render_template('kraj_upitnika.html', jedinstveni_id=jedinstveni_id, odgovori_korisnika=odgovori_korisnika,  vreme=vreme,
        odgovor_pitanje1=odgovor_pitanje1,
        odgovor_pitanje2=odgovor_pitanje2,
        odgovor_pitanje2_text=odgovor_pitanje2_text,
        odgovor_pitanje3=odgovor_pitanje3,
        odgovor_pitanje3_text=odgovor_pitanje3_text,
        odgovor_pitanje4=odgovor_pitanje4,
        odgovor_pitanje5=odgovor_pitanje5,
        odgovor_pitanje5_text=odgovor_pitanje5_text,
        odgovor_pitanje6=odgovor_pitanje6,
        odgovor_pitanje6_text=odgovor_pitanje6_text,
        odgovor_pitanje7=odgovor_pitanje7,
        odgovor_pitanje7_text=odgovor_pitanje7_text,
        odgovor_pitanje8=odgovor_pitanje8,
        odgovor_pitanje8_text=odgovor_pitanje8_text,
        odgovor_pitanje9=odgovor_pitanje9,
        odgovor_pitanje10=odgovor_pitanje10,
        odgovor_pitanje11=odgovor_pitanje11,
        odgovor_pitanje11_text=odgovor_pitanje11_text,
        odgovor_pitanje12=odgovor_pitanje12,
        odgovor_pitanje12_text=odgovor_pitanje12_text,
        odgovor_pitanje13=odgovor_pitanje13,
        odgovor_pitanje13_text=odgovor_pitanje13_text,
        odgovor_pitanje14=odgovor_pitanje14,
        odgovor_pitanje15=odgovor_pitanje15,
        odgovor_pitanje15_text=odgovor_pitanje15_text,
        odgovor_pitanje16=odgovor_pitanje16,
        odgovor_pitanje16_text=odgovor_pitanje16_text,
        odgovor_pitanje17=odgovor_pitanje17,
        odgovor_pitanje17_text=odgovor_pitanje17_text,
        odgovor_pitanje18=odgovor_pitanje18,
        odgovor_pitanje18_text=odgovor_pitanje18_text,
        odgovor_pitanje19=odgovor_pitanje19,
        odgovor_pitanje19_text=odgovor_pitanje19_text,
        odgovor_pitanje20=odgovor_pitanje20,
        odgovor_pitanje20_text=odgovor_pitanje20_text,
        odgovor_pitanje21=odgovor_pitanje21,
        odgovor_pitanje22=odgovor_pitanje22,
        odgovor_pitanje22_text=odgovor_pitanje22_text,
        odgovor_pitanje23=odgovor_pitanje23,
        odgovor_pitanje24=odgovor_pitanje24,
        odgovor_pitanje24_text=odgovor_pitanje24_text,
        odgovor_pitanje25=odgovor_pitanje25,
        odgovor_pitanje25_text=odgovor_pitanje25_text,
        odgovor_pitanje26=odgovor_pitanje26,
        odgovor_pitanje26_text=odgovor_pitanje26_text,
        odgovor_pitanje27=odgovor_pitanje27,
        odgovor_pitanje27_text=odgovor_pitanje27_text,
        odgovor_pitanje28=odgovor_pitanje28,
        odgovor_pitanje29=odgovor_pitanje29,
        odgovor_pitanje29_text=odgovor_pitanje29_text,
        odgovor_pitanje30=odgovor_pitanje30,
        odgovor_pitanje30_text=odgovor_pitanje30_text,
        odgovor_pitanje31=odgovor_pitanje31,
        odgovor_pitanje31_text=odgovor_pitanje31_text,
        odgovor_pitanje32=odgovor_pitanje32,
        odgovor_pitanje32_text=odgovor_pitanje32_text,
        odgovor_pitanje33=odgovor_pitanje33,
        odgovor_pitanje33_text=odgovor_pitanje33_text,
        odgovor_pitanje34=odgovor_pitanje34,
        odgovor_pitanje34_text=odgovor_pitanje34_text,
        odgovor_pitanje35=odgovor_pitanje35,
        odgovor_pitanje35_text=odgovor_pitanje35_text,
        odgovor_pitanje36=odgovor_pitanje36,
        odgovor_pitanje36_text=odgovor_pitanje36_text,
        odgovor_pitanje37=odgovor_pitanje37,
        odgovor_pitanje37_text=odgovor_pitanje37_text,
        odgovor_pitanje38=odgovor_pitanje38,
        odgovor_pitanje38_text=odgovor_pitanje38_text,
        odgovor_pitanje39=odgovor_pitanje39,
        odgovor_pitanje40=odgovor_pitanje40,
        odgovor_pitanje40_text=odgovor_pitanje40_text,
        odgovor_pitanje41=odgovor_pitanje41,
        odgovor_pitanje42=odgovor_pitanje42,
        odgovor_pitanje42_text=odgovor_pitanje42_text,
        odgovor_pitanje43=odgovor_pitanje43,
        odgovor_pitanje43_text=odgovor_pitanje43_text,
        odgovor_pitanje44=odgovor_pitanje44,
        odgovor_pitanje44_text=odgovor_pitanje44_text,
        odgovor_pitanje45=odgovor_pitanje45,
        odgovor_pitanje45_text=odgovor_pitanje45_text,
        odgovor_pitanje46=odgovor_pitanje46,
        odgovor_pitanje46_text=odgovor_pitanje46_text,
        odgovor_pitanje47=odgovor_pitanje47,
        odgovor_pitanje48=odgovor_pitanje48,
        odgovor_pitanje48_text=odgovor_pitanje48_text,
        odgovor_pitanje49=odgovor_pitanje49,
        odgovor_pitanje49_text=odgovor_pitanje49_text,
        odgovor_pitanje50=odgovor_pitanje50,
        odgovor_pitanje51=odgovor_pitanje51,
        odgovor_pitanje52=odgovor_pitanje52,
        odgovor_pitanje53=odgovor_pitanje53,
        odgovor_pitanje54=odgovor_pitanje54,
        odgovor_pitanje54_text=odgovor_pitanje54_text,
        odgovor_pitanje55=odgovor_pitanje55,
        odgovor_pitanje56=odgovor_pitanje56,
        odgovor_pitanje57=odgovor_pitanje57,
        odgovor_pitanje57_text=odgovor_pitanje57_text,
        odgovor_pitanje58=odgovor_pitanje58,
        odgovor_pitanje59=odgovor_pitanje59,
        odgovor_pitanje60=odgovor_pitanje60,
        odgovor_pitanje60_text=odgovor_pitanje60_text,
        odgovor_pitanje61=odgovor_pitanje61,
        odgovor_pitanje62=odgovor_pitanje62,
        odgovor_pitanje62_text=odgovor_pitanje62_text,
        odgovor_pitanje63=odgovor_pitanje63,
        odgovor_pitanje64=odgovor_pitanje64,
        odgovor_pitanje64_text=odgovor_pitanje64_text,
        odgovor_pitanje65=odgovor_pitanje65,
        odgovor_pitanje65_text=odgovor_pitanje65_text,
        odgovor_pitanje66=odgovor_pitanje66,
        odgovor_pitanje66_text=odgovor_pitanje66_text,
        odgovor_pitanje67=odgovor_pitanje67,
        odgovor_pitanje67_text=odgovor_pitanje67_text,
        odgovor_pitanje68=odgovor_pitanje68,
        odgovor_pitanje69=odgovor_pitanje69,
        odgovor_pitanje69_text=odgovor_pitanje69_text,
        odgovor_pitanje70=odgovor_pitanje70,
        odgovor_pitanje70_text=odgovor_pitanje70_text,
        odgovor_pitanje71=odgovor_pitanje71,
        odgovor_pitanje71_text=odgovor_pitanje71_text,
        odgovor_pitanje72=odgovor_pitanje72,
        odgovor_pitanje73=odgovor_pitanje73,
        odgovor_pitanje74=odgovor_pitanje74,
        odgovor_pitanje75=odgovor_pitanje75,
        odgovor_pitanje75_text=odgovor_pitanje75_text,
        odgovor_pitanje76=odgovor_pitanje76,
        odgovor_pitanje77=odgovor_pitanje77,
        odgovor_pitanje78=odgovor_pitanje78,
        odgovor_pitanje79=odgovor_pitanje79,
        odgovor_pitanje80=odgovor_pitanje80,
        odgovor_pitanje81=odgovor_pitanje81,
        odgovor_pitanje82=odgovor_pitanje82,
        odgovor_pitanje82_text=odgovor_pitanje82_text,
        odgovor_pitanje83=odgovor_pitanje83,
        odgovor_pitanje83_text=odgovor_pitanje83_text,
        odgovor_pitanje84=odgovor_pitanje84,
        odgovor_pitanje84_text=odgovor_pitanje84_text,
        odgovor_pitanje85=odgovor_pitanje85,
        odgovor_pitanje86=odgovor_pitanje86,
        odgovor_pitanje86_text=odgovor_pitanje86_text,
        odgovor_pitanje87=odgovor_pitanje87,
        odgovor_pitanje87_text=odgovor_pitanje87_text,
        odgovor_pitanje88=odgovor_pitanje88,
        odgovor_pitanje88_text=odgovor_pitanje88_text,
        odgovor_pitanje89=odgovor_pitanje89,
        odgovor_pitanje89_text=odgovor_pitanje89_text,
        odgovor_pitanje90=odgovor_pitanje90,
        odgovor_pitanje91=odgovor_pitanje91,
        odgovor_pitanje92=odgovor_pitanje92,
        odgovor_pitanje92_text=odgovor_pitanje92_text,
        odgovor_pitanje93=odgovor_pitanje93,
        odgovor_pitanje94=odgovor_pitanje94,
        odgovor_pitanje94_text=odgovor_pitanje94_text,
        odgovor_pitanje95=odgovor_pitanje95,
        odgovor_pitanje96=odgovor_pitanje96,
        odgovor_pitanje97=odgovor_pitanje97,
        odgovor_pitanje98=odgovor_pitanje98,
        odgovor_pitanje99=odgovor_pitanje99,
        odgovor_pitanje100=odgovor_pitanje100,
        odgovor_pitanje100_text=odgovor_pitanje100_text,
        odgovor_pitanje101=odgovor_pitanje101,
        odgovor_pitanje101_text=odgovor_pitanje101_text,
        odgovor_pitanje102=odgovor_pitanje102,
        odgovor_pitanje103=odgovor_pitanje103,
        odgovor_pitanje104=odgovor_pitanje104,
        odgovor_pitanje104_text=odgovor_pitanje104_text,
        odgovor_pitanje105=odgovor_pitanje105,
        odgovor_pitanje105_text=odgovor_pitanje105_text,
        odgovor_pitanje106=odgovor_pitanje106,
        odgovor_pitanje106_text=odgovor_pitanje106_text,
        odgovor_pitanje107=odgovor_pitanje107,
        odgovor_pitanje108=odgovor_pitanje108,
        odgovor_pitanje109=odgovor_pitanje109,
        odgovor_pitanje110=odgovor_pitanje110,
        odgovor_pitanje111=odgovor_pitanje111,
        odgovor_pitanje112=odgovor_pitanje112      
)


@app.route('/preuzmi_pdf', methods=['GET'])
def preuzmi_pdf_fajl():
   # Provera da li korisnik ima jedinstveni ID u sesiji
    if 'jedinstveni_id' in request.cookies:
        # Ako postoji jedinstveni ID u sesiji, koristimo ga
        jedinstveni_id = request.cookies['jedinstveni_id']
    else:
        # Ako ne postoji jedinstveni ID u sesiji, korisnik nije pravilno započeo upitnik, preusmeravamo ga na početnu stranicu
        return redirect(url_for('index'))

    # Dohvatanje odgovora i pitanja iz baze podataka na osnovu jedinstvenog ID-ja
    odgovori_korisnika = dohvati_odgovore_korisnika(jedinstveni_id)

    # Dobijanje trenutnog vremena
    vreme = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Dohvatanje odgovora iz sesije
    odgovor_pitanje1 = session.get('pitanje1', '')
    odgovor_pitanje2 = session.get('pitanje2', '')
    odgovor_pitanje2_text = session.get('pitanje2_text', '')
    odgovor_pitanje3 = session.get('pitanje3', '')
    odgovor_pitanje3_text = session.get('pitanje3_text', '')
    odgovor_pitanje4 = session.get('pitanje4', '')
    odgovor_pitanje5 = session.get('pitanje5', '')
    odgovor_pitanje5_text = session.get('pitanje5_text', '')
    odgovor_pitanje6 = session.get('pitanje6', '')
    odgovor_pitanje6_text = session.get('pitanje6_text', '')
    odgovor_pitanje7 = session.get('pitanje7', '')
    odgovor_pitanje7_text = session.get('pitanje7_text', '')
    odgovor_pitanje8 = session.get('pitanje8', '')
    odgovor_pitanje8_text = session.get('pitanje8_text', '')
    odgovor_pitanje9 = session.get('pitanje9', '')
    odgovor_pitanje10 = session.get('pitanje10', '')
    odgovor_pitanje11 = session.get('pitanje11', '')
    odgovor_pitanje11_text = session.get('pitanje11_text', '')
    odgovor_pitanje12 = session.get('pitanje12', '')
    odgovor_pitanje12_text = session.get('pitanje12_text', '')
    odgovor_pitanje13 = session.get('pitanje13', '')
    odgovor_pitanje13_text = session.get('pitanje13_text', '')
    odgovor_pitanje14 = session.get('pitanje14', '')
    odgovor_pitanje15 = session.get('pitanje15', '')
    odgovor_pitanje15_text = session.get('pitanje15_text', '')
    odgovor_pitanje16 = session.get('pitanje16', '')
    odgovor_pitanje16_text = session.get('pitanje16_text', '')
    odgovor_pitanje17 = session.get('pitanje17', '')
    odgovor_pitanje17_text = session.get('pitanje17_text', '')
    odgovor_pitanje18 = session.get('pitanje18', [])
    odgovor_pitanje18_text = session.get('pitanje18_text', '')
    odgovor_pitanje19 = session.get('pitanje19', '')
    odgovor_pitanje19_text = session.get('pitanje19_text', '')
    odgovor_pitanje20 = session.get('pitanje20', '')
    odgovor_pitanje20_text = session.get('pitanje20_text', '')
    odgovor_pitanje21 = session.get('pitanje21', '')
    odgovor_pitanje22 = session.get('pitanje22', '')
    odgovor_pitanje22_text = session.get('pitanje22_text', '')
    odgovor_pitanje23 = session.get('pitanje23', '')
    odgovor_pitanje24 = session.get('pitanje24', '')
    odgovor_pitanje24_text = session.get('pitanje24_text', '')
    odgovor_pitanje25 = session.get('pitanje25', '')
    odgovor_pitanje25_text = session.get('pitanje25_text', '')
    odgovor_pitanje26 = session.get('pitanje26', '')
    odgovor_pitanje26_text = session.get('pitanje26_text', '')
    odgovor_pitanje27 = session.get('pitanje27', '')
    odgovor_pitanje27_text = session.get('pitanje27_text', '')
    odgovor_pitanje28 = session.get('pitanje28', '')
    odgovor_pitanje29 = session.get('pitanje29', '')
    odgovor_pitanje29_text = session.get('pitanje29_text', '')
    odgovor_pitanje30 = session.get('pitanje30', '')
    odgovor_pitanje30_text = session.get('pitanje30_text', '')
    odgovor_pitanje31 = session.get('pitanje31', '')
    odgovor_pitanje31_text = session.get('pitanje31_text', '')
    odgovor_pitanje32 = session.get('pitanje32', '')
    odgovor_pitanje32_text = session.get('pitanje32_text', '')
    odgovor_pitanje33 = session.get('pitanje33', '')
    odgovor_pitanje33_text = session.get('pitanje33_text', '')
    odgovor_pitanje34 = session.get('pitanje34', '')
    odgovor_pitanje34_text = session.get('pitanje34_text', '')
    odgovor_pitanje35 = session.get('pitanje35', '')
    odgovor_pitanje35_text = session.get('pitanje35_text', '')
    odgovor_pitanje36 = session.get('pitanje36', '')
    odgovor_pitanje36_text = session.get('pitanje36_text', '')
    odgovor_pitanje37 = session.get('pitanje37', '')
    odgovor_pitanje37_text = session.get('pitanje37_text', '')
    odgovor_pitanje38 = session.get('pitanje38', '')
    odgovor_pitanje38_text = session.get('pitanje38_text', '')
    odgovor_pitanje39 = session.get('pitanje39', '')
    odgovor_pitanje40 = session.get('pitanje40', '')
    odgovor_pitanje40_text = session.get('pitanje40_text', '')
    odgovor_pitanje41 = session.get('pitanje41', '')
    odgovor_pitanje42 = session.get('pitanje42', '')
    odgovor_pitanje42_text = session.get('pitanje42_text', '')
    odgovor_pitanje43 = session.get('pitanje43', [])
    odgovor_pitanje43_text = session.get('pitanje43_text', '')
    odgovor_pitanje44 = session.get('pitanje44', '')
    odgovor_pitanje44_text = session.get('pitanje44_text', '')
    odgovor_pitanje45 = session.get('pitanje45', '')
    odgovor_pitanje45_text = session.get('pitanje45_text', '')
    odgovor_pitanje46 = session.get('pitanje46', [])
    odgovor_pitanje46_text = session.get('pitanje46_text', '')
    odgovor_pitanje47 = session.get('pitanje47', '')
    odgovor_pitanje48 = session.get('pitanje48', '')
    odgovor_pitanje48_text = session.get('pitanje48_text', '')
    odgovor_pitanje49 = session.get('pitanje49', '')
    odgovor_pitanje49_text = session.get('pitanje49_text', '')
    odgovor_pitanje50 = session.get('pitanje50', [])
    odgovor_pitanje51 = session.get('pitanje51', '')
    odgovor_pitanje52 = session.get('pitanje52', '')
    odgovor_pitanje53 = session.get('pitanje53', '')
    odgovor_pitanje54 = session.get('pitanje54', '')
    odgovor_pitanje54_text = session.get('pitanje54_text', '')
    odgovor_pitanje55 = session.get('pitanje55', '')
    odgovor_pitanje56 = session.get('pitanje56', '')
    odgovor_pitanje57 = session.get('pitanje57', [])
    odgovor_pitanje57_text = session.get('pitanje57_text', '')
    odgovor_pitanje58 = session.get('pitanje58', '')
    odgovor_pitanje59 = session.get('pitanje59', '')
    odgovor_pitanje60 = session.get('pitanje60', [])
    odgovor_pitanje60_text = session.get('pitanje60_text', '')
    odgovor_pitanje61 = session.get('pitanje61', '')
    odgovor_pitanje62 = session.get('pitanje62', '')
    odgovor_pitanje62_text = session.get('pitanje62_text', '')
    odgovor_pitanje63 = session.get('pitanje63', '')
    odgovor_pitanje64 = session.get('pitanje64', '')
    odgovor_pitanje64_text = session.get('pitanje64_text', '')
    odgovor_pitanje65 = session.get('pitanje65', [])
    odgovor_pitanje65_text = session.get('pitanje65_text', '')
    odgovor_pitanje66 = session.get('pitanje66', '')
    odgovor_pitanje66_text = session.get('pitanje66_text', '')
    odgovor_pitanje67 = session.get('pitanje67', '')
    odgovor_pitanje67_text = session.get('pitanje67_text', '')
    odgovor_pitanje68 = session.get('pitanje68', '')
    odgovor_pitanje69 = session.get('pitanje69', '')
    odgovor_pitanje69_text = session.get('pitanje69_text', '')
    odgovor_pitanje70 = session.get('pitanje70', '')
    odgovor_pitanje70_text = session.get('pitanje70_text', '')
    odgovor_pitanje71 = session.get('pitanje71', '')
    odgovor_pitanje71_text = session.get('pitanje71_text', '')
    odgovor_pitanje72 = session.get('pitanje72', '')
    odgovor_pitanje73 = session.get('pitanje73', '')
    odgovor_pitanje74 = session.get('pitanje74', '')
    odgovor_pitanje75 = session.get('pitanje75', '')
    odgovor_pitanje75_text = session.get('pitanje75_text', '')
    odgovor_pitanje76 = session.get('pitanje76', '')
    odgovor_pitanje77 = session.get('pitanje77', '')
    odgovor_pitanje78 = session.get('pitanje78', '')
    odgovor_pitanje79 = session.get('pitanje79', '')
    odgovor_pitanje80 = session.get('pitanje80', '')
    odgovor_pitanje81 = session.get('pitanje81', '')
    odgovor_pitanje82 = session.get('pitanje82', '')
    odgovor_pitanje82_text = session.get('pitanje82_text', '')
    odgovor_pitanje83 = session.get('pitanje83', '')
    odgovor_pitanje83_text = session.get('pitanje83_text', '')
    odgovor_pitanje84 = session.get('pitanje84', '')
    odgovor_pitanje84_text = session.get('pitanje84_text', '')
    odgovor_pitanje85 = session.get('pitanje85', '')
    odgovor_pitanje86 = session.get('pitanje86', '')
    odgovor_pitanje86_text = session.get('pitanje86_text', '')
    odgovor_pitanje87 = session.get('pitanje87', '')
    odgovor_pitanje87_text = session.get('pitanje87_text', '')
    odgovor_pitanje88 = session.get('pitanje88', '')
    odgovor_pitanje88_text = session.get('pitanje88_text', '')
    odgovor_pitanje89 = session.get('pitanje89', '')
    odgovor_pitanje89_text = session.get('pitanje89_text', '')
    odgovor_pitanje90 = session.get('pitanje90', '')
    odgovor_pitanje91 = session.get('pitanje91', '')
    odgovor_pitanje92 = session.get('pitanje92', '')
    odgovor_pitanje92_text = session.get('pitanje92_text', '')
    odgovor_pitanje93 = session.get('pitanje93', '')
    odgovor_pitanje94 = session.get('pitanje94', '')
    odgovor_pitanje94_text = session.get('pitanje94_text', '')
    odgovor_pitanje95 = session.get('pitanje95', '')
    odgovor_pitanje96 = session.get('pitanje96', '')
    odgovor_pitanje97 = session.get('pitanje97', '')
    odgovor_pitanje98 = session.get('pitanje98', '')
    odgovor_pitanje99 = session.get('pitanje99', '')
    odgovor_pitanje100 = session.get('pitanje100', '')
    odgovor_pitanje100_text = session.get('pitanje100_text', '')
    odgovor_pitanje101 = session.get('pitanje101', '')
    odgovor_pitanje101_text = session.get('pitanje101_text', '')
    odgovor_pitanje102 = session.get('pitanje102', '')
    odgovor_pitanje103 = session.get('pitanje103', '')
    odgovor_pitanje104 = session.get('pitanje104', '')
    odgovor_pitanje104_text = session.get('pitanje104_text', '')
    odgovor_pitanje105 = session.get('pitanje105', '')
    odgovor_pitanje105_text = session.get('pitanje105_text', '')
    odgovor_pitanje106 = session.get('pitanje106', '')
    odgovor_pitanje106_text = session.get('pitanje106_text', '')
    odgovor_pitanje107 = session.get('pitanje107', '')
    odgovor_pitanje108 = session.get('pitanje108', '')
    odgovor_pitanje109 = session.get('pitanje109', '')
    odgovor_pitanje110 = session.get('pitanje110', '')
    odgovor_pitanje111 = session.get('pitanje111', '')
    odgovor_pitanje112 = session.get('pitanje112', '')


     


                       # Generiši HTML iz šablona koristeći Jinja2
    rendered_html = render_template('pdf_template.html', jedinstveni_id=jedinstveni_id, odgovori_korisnika=odgovori_korisnika,  vreme=vreme,
                                    odgovor_pitanje1=odgovor_pitanje1,
                                    odgovor_pitanje2=odgovor_pitanje2,
                                    odgovor_pitanje2_text=odgovor_pitanje2_text,
                                    odgovor_pitanje3=odgovor_pitanje3,
                                    odgovor_pitanje3_text=odgovor_pitanje3_text,
                                    odgovor_pitanje4=odgovor_pitanje4,
                                    odgovor_pitanje5=odgovor_pitanje5,
                                    odgovor_pitanje5_text=odgovor_pitanje5_text,
                                    odgovor_pitanje6=odgovor_pitanje6,
                                    odgovor_pitanje6_text=odgovor_pitanje6_text,
                                    odgovor_pitanje7=odgovor_pitanje7,
                                    odgovor_pitanje7_text=odgovor_pitanje7_text,
                                    odgovor_pitanje8=odgovor_pitanje8,
                                    odgovor_pitanje8_text=odgovor_pitanje8_text,
                                    odgovor_pitanje9=odgovor_pitanje9,
                                    odgovor_pitanje10=odgovor_pitanje10,
                                    odgovor_pitanje11=odgovor_pitanje11,
                                    odgovor_pitanje11_text=odgovor_pitanje11_text,
                                    odgovor_pitanje12=odgovor_pitanje12,
                                    odgovor_pitanje12_text=odgovor_pitanje12_text,
                                    odgovor_pitanje13=odgovor_pitanje13,
                                    odgovor_pitanje13_text=odgovor_pitanje13_text,
                                    odgovor_pitanje14=odgovor_pitanje14,
                                    odgovor_pitanje15=odgovor_pitanje15,
                                    odgovor_pitanje15_text=odgovor_pitanje15_text,
                                    odgovor_pitanje16=odgovor_pitanje16,
                                    odgovor_pitanje16_text=odgovor_pitanje16_text,
                                    odgovor_pitanje17=odgovor_pitanje17,
                                    odgovor_pitanje17_text=odgovor_pitanje17_text,
                                    odgovor_pitanje18=odgovor_pitanje18,
                                    odgovor_pitanje18_text=odgovor_pitanje18_text,
                                    odgovor_pitanje19=odgovor_pitanje19,
                                    odgovor_pitanje19_text=odgovor_pitanje19_text,
                                    odgovor_pitanje20=odgovor_pitanje20,
                                    odgovor_pitanje20_text=odgovor_pitanje20_text,
                                    odgovor_pitanje21=odgovor_pitanje21,
                                    odgovor_pitanje22=odgovor_pitanje22,
                                    odgovor_pitanje22_text=odgovor_pitanje22_text,
                                    odgovor_pitanje23=odgovor_pitanje23,
                                    odgovor_pitanje24=odgovor_pitanje24,
                                    odgovor_pitanje24_text=odgovor_pitanje24_text,
                                    odgovor_pitanje25=odgovor_pitanje25,
                                    odgovor_pitanje25_text=odgovor_pitanje25_text,
                                    odgovor_pitanje26=odgovor_pitanje26,
                                    odgovor_pitanje26_text=odgovor_pitanje26_text,
                                    odgovor_pitanje27=odgovor_pitanje27,
                                    odgovor_pitanje27_text=odgovor_pitanje27_text,
                                    odgovor_pitanje28=odgovor_pitanje28,
                                    odgovor_pitanje29=odgovor_pitanje29,
                                    odgovor_pitanje29_text=odgovor_pitanje29_text,
                                    odgovor_pitanje30=odgovor_pitanje30,
                                    odgovor_pitanje30_text=odgovor_pitanje30_text,
                                    odgovor_pitanje31=odgovor_pitanje31,
                                    odgovor_pitanje31_text=odgovor_pitanje31_text,
                                    odgovor_pitanje32=odgovor_pitanje32,
                                    odgovor_pitanje32_text=odgovor_pitanje32_text,
                                    odgovor_pitanje33=odgovor_pitanje33,
                                    odgovor_pitanje33_text=odgovor_pitanje33_text,
                                    odgovor_pitanje34=odgovor_pitanje34,
                                    odgovor_pitanje34_text=odgovor_pitanje34_text,
                                    odgovor_pitanje35=odgovor_pitanje35,
                                    odgovor_pitanje35_text=odgovor_pitanje35_text,
                                    odgovor_pitanje36=odgovor_pitanje36,
                                    odgovor_pitanje36_text=odgovor_pitanje36_text,
                                    odgovor_pitanje37=odgovor_pitanje37,
                                    odgovor_pitanje37_text=odgovor_pitanje37_text,
                                    odgovor_pitanje38=odgovor_pitanje38,
                                    odgovor_pitanje38_text=odgovor_pitanje38_text,
                                    odgovor_pitanje39=odgovor_pitanje39,
                                    odgovor_pitanje40=odgovor_pitanje40,
                                    odgovor_pitanje40_text=odgovor_pitanje40_text,
                                    odgovor_pitanje41=odgovor_pitanje41,
                                    odgovor_pitanje42=odgovor_pitanje42,
                                    odgovor_pitanje42_text=odgovor_pitanje42_text,
                                    odgovor_pitanje43=odgovor_pitanje43,
                                    odgovor_pitanje43_text=odgovor_pitanje43_text,
                                    odgovor_pitanje44=odgovor_pitanje44,
                                    odgovor_pitanje44_text=odgovor_pitanje44_text,
                                    odgovor_pitanje45=odgovor_pitanje45,
                                    odgovor_pitanje45_text=odgovor_pitanje45_text,
                                    odgovor_pitanje46=odgovor_pitanje46,
                                    odgovor_pitanje46_text=odgovor_pitanje46_text,
                                    odgovor_pitanje47=odgovor_pitanje47,
                                    odgovor_pitanje48=odgovor_pitanje48,
                                    odgovor_pitanje48_text=odgovor_pitanje48_text,
                                    odgovor_pitanje49=odgovor_pitanje49,
                                    odgovor_pitanje49_text=odgovor_pitanje49_text,
                                    odgovor_pitanje50=odgovor_pitanje50,
                                    odgovor_pitanje51=odgovor_pitanje51,
                                    odgovor_pitanje52=odgovor_pitanje52,
                                    odgovor_pitanje53=odgovor_pitanje53,
                                    odgovor_pitanje54=odgovor_pitanje54,
                                    odgovor_pitanje54_text=odgovor_pitanje54_text,
                                    odgovor_pitanje55=odgovor_pitanje55,
                                    odgovor_pitanje56=odgovor_pitanje56,
                                    odgovor_pitanje57=odgovor_pitanje57,
                                    odgovor_pitanje57_text=odgovor_pitanje57_text,
                                    odgovor_pitanje58=odgovor_pitanje58,
                                    odgovor_pitanje59=odgovor_pitanje59,
                                    odgovor_pitanje60=odgovor_pitanje60,
                                    odgovor_pitanje60_text=odgovor_pitanje60_text,
                                    odgovor_pitanje61=odgovor_pitanje61,
                                    odgovor_pitanje62=odgovor_pitanje62,
                                    odgovor_pitanje62_text=odgovor_pitanje62_text,
                                    odgovor_pitanje63=odgovor_pitanje63,
                                    odgovor_pitanje64=odgovor_pitanje64,
                                    odgovor_pitanje64_text=odgovor_pitanje64_text,
                                    odgovor_pitanje65=odgovor_pitanje65,
                                    odgovor_pitanje65_text=odgovor_pitanje65_text,
                                    odgovor_pitanje66=odgovor_pitanje66,
                                    odgovor_pitanje66_text=odgovor_pitanje66_text,
                                    odgovor_pitanje67=odgovor_pitanje67,
                                    odgovor_pitanje67_text=odgovor_pitanje67_text,
                                    odgovor_pitanje68=odgovor_pitanje68,
                                    odgovor_pitanje69=odgovor_pitanje69,
                                    odgovor_pitanje69_text=odgovor_pitanje69_text,
                                    odgovor_pitanje70=odgovor_pitanje70,
                                    odgovor_pitanje70_text=odgovor_pitanje70_text,
                                    odgovor_pitanje71=odgovor_pitanje71,
                                    odgovor_pitanje71_text=odgovor_pitanje71_text,
                                    odgovor_pitanje72=odgovor_pitanje72,
                                    odgovor_pitanje73=odgovor_pitanje73,
                                    odgovor_pitanje74=odgovor_pitanje74,
                                    odgovor_pitanje75=odgovor_pitanje75,
                                    odgovor_pitanje75_text=odgovor_pitanje75_text,
                                    odgovor_pitanje76=odgovor_pitanje76,
                                    odgovor_pitanje77=odgovor_pitanje77,
                                    odgovor_pitanje78=odgovor_pitanje78,
                                    odgovor_pitanje79=odgovor_pitanje79,
                                    odgovor_pitanje80=odgovor_pitanje80,
                                    odgovor_pitanje81=odgovor_pitanje81,
                                    odgovor_pitanje82=odgovor_pitanje82,
                                    odgovor_pitanje82_text=odgovor_pitanje82_text,
                                    odgovor_pitanje83=odgovor_pitanje83,
                                    odgovor_pitanje83_text=odgovor_pitanje83_text,
                                    odgovor_pitanje84=odgovor_pitanje84,
                                    odgovor_pitanje84_text=odgovor_pitanje84_text,
                                    odgovor_pitanje85=odgovor_pitanje85,
                                    odgovor_pitanje86=odgovor_pitanje86,
                                    odgovor_pitanje86_text=odgovor_pitanje86_text,
                                    odgovor_pitanje87=odgovor_pitanje87,
                                    odgovor_pitanje87_text=odgovor_pitanje87_text,
                                    odgovor_pitanje88=odgovor_pitanje88,
                                    odgovor_pitanje88_text=odgovor_pitanje88_text,
                                    odgovor_pitanje89=odgovor_pitanje89,
                                    odgovor_pitanje89_text=odgovor_pitanje89_text,
                                    odgovor_pitanje90=odgovor_pitanje90,
                                    odgovor_pitanje91=odgovor_pitanje91,
                                    odgovor_pitanje92=odgovor_pitanje92,
                                    odgovor_pitanje92_text=odgovor_pitanje92_text,
                                    odgovor_pitanje93=odgovor_pitanje93,
                                    odgovor_pitanje94=odgovor_pitanje94,
                                    odgovor_pitanje94_text=odgovor_pitanje94_text,
                                    odgovor_pitanje95=odgovor_pitanje95,
                                    odgovor_pitanje96=odgovor_pitanje96,
                                    odgovor_pitanje97=odgovor_pitanje97,
                                    odgovor_pitanje98=odgovor_pitanje98,
                                    odgovor_pitanje99=odgovor_pitanje99,
                                    odgovor_pitanje100=odgovor_pitanje100,
                                    odgovor_pitanje100_text=odgovor_pitanje100_text,
                                    odgovor_pitanje101=odgovor_pitanje101,
                                    odgovor_pitanje101_text=odgovor_pitanje101_text,
                                    odgovor_pitanje102=odgovor_pitanje102,
                                    odgovor_pitanje103=odgovor_pitanje103,
                                    odgovor_pitanje104=odgovor_pitanje104,
                                    odgovor_pitanje104_text=odgovor_pitanje104_text,
                                    odgovor_pitanje105=odgovor_pitanje105,
                                    odgovor_pitanje105_text=odgovor_pitanje105_text,
                                    odgovor_pitanje106=odgovor_pitanje106,
                                    odgovor_pitanje106_text=odgovor_pitanje106_text,
                                    odgovor_pitanje107=odgovor_pitanje107,
                                    odgovor_pitanje108=odgovor_pitanje108,
                                    odgovor_pitanje109=odgovor_pitanje109,
                                    odgovor_pitanje110=odgovor_pitanje110,
                                    odgovor_pitanje111=odgovor_pitanje111,
                                    odgovor_pitanje112=odgovor_pitanje112   
                                    # Dodajte ostale odgovore ovde
                                    )
    # Kreirajte PDF koristeći FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.add_font("DejaVuSans", fname="upitnik_app/static/font/DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVuSans", size=12)  # Postavite font na DejaVuSans ili drugi font koji podržava ćirilicu

    # Zatim dodajte svoj tekst u PDF
    pdf.multi_cell(0, 5, txt=rendered_html, border=0, align='L')

    # Sačuvajte PDF fajl
    pdf_file_path = os.path.join(os.getcwd(), 'pdf_odgovori', f'odgovori_{jedinstveni_id}.pdf')
    pdf.output(pdf_file_path)

        # Definišite putanju do PDF fajla
    pdf_file_path = os.path.join(os.getcwd(), 'pdf_odgovori', f'odgovori_{jedinstveni_id}.pdf')

    # Vratite PDF fajl korisniku za preuzimanje
    return send_file(pdf_file_path, as_attachment=True, download_name=f'odgovori_{jedinstveni_id}.pdf')



if __name__ == '__main__':
    app.run(debug=True)
