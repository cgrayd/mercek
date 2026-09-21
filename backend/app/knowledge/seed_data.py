"""Bilgi tabani tohum verisi.

Kaynaklar:

- ASVS omurgadir. OWASP Top 10 kategorik ve farkindalik odakli oldugu,
  getirme icin fazla kaba kaldigi icin tercih edilmemistir; ASVS'in her
  maddesi atomik ve dogrulanabilir bir gereksinim cumlesidir.
- LINDDUN mahremiyet kolunun akademik dayanagidir.
- CWE spesifik zafiyet tanimlari icin kullanilir.
- KVKK ve GDPR hukuki kolu besler.
- Saglayici politikalari, bir teknolojinin veriyi nasil isledigi sorusunu
  cevaplar.

Uretimde bu liste tam ASVS ve CWE korpusuyla degistirilmelidir
(`ingest.py --asvs <dosya>`). Buradaki set sistemin ilk kurulumda anlamli
cikti uretmesi icin yeterlidir.
"""

TOHUM: list[dict] = [
    # ------------------------------------------------------------ ASVS
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 1.5.2", "dil": "en",
     "baslik": "Serialization and deserialization of untrusted data",
     "metin": "Verify that serialization is not used when communicating with untrusted "
              "clients. Deserialization of untrusted data enables remote code execution "
              "and object injection. Where serialization must be used, integrity checks "
              "or encryption must prevent hostile object creation or data tampering."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 2.1.7", "dil": "en",
     "baslik": "Password credential storage and breach checking",
     "metin": "Verify that passwords are checked against a set of breached passwords. "
              "Credentials must never be stored in plaintext or with reversible encryption. "
              "Use a memory-hard key derivation function such as argon2id, scrypt or bcrypt."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 3.5.3", "dil": "en",
     "baslik": "Stateless token validation",
     "metin": "Verify that stateless tokens such as JWT use digital signatures, encryption "
              "and other countermeasures to protect against tampering, enveloping, replay, "
              "null cipher and key substitution attacks. Tokens transmitted to the client "
              "must be treated as untrusted input on return."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 4.1.3", "dil": "en",
     "baslik": "Principle of least privilege in access control",
     "metin": "Verify that the principle of least privilege exists: users can only access "
              "functions, data files, URLs, controllers, services and other resources for "
              "which they possess specific authorization. This implies protection against "
              "spoofing and elevation of privilege."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 4.2.1", "dil": "en",
     "baslik": "Object level authorization",
     "metin": "Verify that sensitive data and APIs are protected against Insecure Direct "
              "Object Reference attacks targeting creation, reading, updating and deletion "
              "of records. Authorization must be checked on every request against the "
              "specific object identifier supplied by the client."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 6.2.1", "dil": "en",
     "baslik": "Cryptographic algorithm selection",
     "metin": "Verify that all cryptographic modules fail securely and that errors are "
              "handled so as not to enable padding oracle attacks. Custom or proprietary "
              "cryptographic algorithms must not be used. Approved algorithms and modes "
              "such as AES-GCM must be selected."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 8.1.1", "dil": "en",
     "baslik": "Sensitive data in logs and caches",
     "metin": "Verify that the application protects sensitive data from being cached in "
              "server components such as load balancers and application caches. Log files "
              "must not contain credentials, session tokens, payment data or other "
              "sensitive information."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 8.3.4", "dil": "en",
     "baslik": "Inventory of sensitive data collected",
     "metin": "Verify that all sensitive data created and processed by the application has "
              "been identified, and that a policy exists on how to deal with it. An "
              "inventory of what personal data is collected, where it is stored, how long "
              "it is retained and which third parties receive it is a prerequisite for "
              "any privacy control."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 9.1.1", "dil": "en",
     "baslik": "Encryption of data in transit",
     "metin": "Verify that TLS is used for all client connectivity and does not fall back "
              "to insecure or unencrypted communications. Connections to and from backend "
              "services and third-party APIs must be authenticated and encrypted; internal "
              "traffic must not be assumed trusted merely because it is internal."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 12.1.1", "dil": "en",
     "baslik": "File upload size and type restrictions",
     "metin": "Verify that the application will not accept large files that could fill up "
              "storage or cause a denial of service. Uploaded file types, sizes and content "
              "must be validated server-side; files must be stored outside the web root or "
              "served from a separate domain without execution permissions."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 14.2.1", "dil": "en",
     "baslik": "Dependency and component currency",
     "metin": "Verify that all components are up to date, preferably using a dependency "
              "checker during build or compile time. Third-party libraries with known "
              "vulnerabilities create supply chain exposure that is invisible in the "
              "application's own source code."},
    {"kaynak_turu": "asvs", "kaynak_kimlik": "ASVS 14.3.2", "dil": "en",
     "baslik": "Debug modes and verbose error output",
     "metin": "Verify that debug modes are disabled in production and that error messages "
              "do not disclose stack traces, framework versions, internal hostnames or "
              "database structure. Verbose diagnostics assist attackers in reconnaissance."},

    # ------------------------------------------------------------ CWE
    {"kaynak_turu": "cwe", "kaynak_kimlik": "CWE-311", "dil": "en",
     "baslik": "Missing encryption of sensitive data",
     "metin": "The product does not encrypt sensitive or critical information before "
              "storage or transmission. Omission of encryption at rest means anyone with "
              "filesystem, backup or database-dump access can read the data directly. "
              "Design documents that describe storage without describing encryption leave "
              "this control unverified.",
     "url": "https://cwe.mitre.org/data/definitions/311.html"},
    {"kaynak_turu": "cwe", "kaynak_kimlik": "CWE-359", "dil": "en",
     "baslik": "Exposure of private personal information to an unauthorized actor",
     "metin": "The product does not properly prevent a person's private personal "
              "information from being accessed by actors who either (1) are not explicitly "
              "authorized to access the information or (2) do not have the implicit consent "
              "of the person about whom the information is collected.",
     "url": "https://cwe.mitre.org/data/definitions/359.html"},
    {"kaynak_turu": "cwe", "kaynak_kimlik": "CWE-522", "dil": "en",
     "baslik": "Insufficiently protected credentials",
     "metin": "The product transmits or stores authentication credentials using an "
              "insecure method that is susceptible to unauthorized interception or "
              "retrieval. API keys committed to source control or embedded in mobile "
              "clients are a common instance of this weakness.",
     "url": "https://cwe.mitre.org/data/definitions/522.html"},
    {"kaynak_turu": "cwe", "kaynak_kimlik": "CWE-798", "dil": "en",
     "baslik": "Use of hard-coded credentials",
     "metin": "The product contains hard-coded credentials such as a password or "
              "cryptographic key for inbound authentication or outbound communication. "
              "Credentials placed in client-side code or configuration files shipped with "
              "the application can be extracted by anyone who obtains the artifact.",
     "url": "https://cwe.mitre.org/data/definitions/798.html"},
    {"kaynak_turu": "cwe", "kaynak_kimlik": "CWE-89", "dil": "en",
     "baslik": "SQL injection",
     "metin": "The product constructs SQL commands using externally-influenced input "
              "without neutralizing special elements. Parameterized queries or prepared "
              "statements are the primary control; string concatenation of user input into "
              "query text is the primary cause.",
     "url": "https://cwe.mitre.org/data/definitions/89.html"},
    {"kaynak_turu": "cwe", "kaynak_kimlik": "CWE-1230", "dil": "en",
     "baslik": "Exposure of sensitive information through metadata",
     "metin": "The product prevents direct access to a resource containing sensitive "
              "information, but it does not sufficiently limit access to metadata derived "
              "from that resource. Image EXIF data containing GPS coordinates is a common "
              "example in applications that accept user photo uploads.",
     "url": "https://cwe.mitre.org/data/definitions/1230.html"},

    # ------------------------------------------------------------ LINDDUN
    {"kaynak_turu": "linddun", "kaynak_kimlik": "LINDDUN-L", "dil": "en",
     "baslik": "Linkability",
     "metin": "An adversary is able to link two items of interest without knowing the "
              "identity of the data subject involved. Persistent device identifiers, "
              "session cookies reused across contexts, and shared user IDs across "
              "microservices allow separate records to be joined into a profile even when "
              "each record alone is anonymous."},
    {"kaynak_turu": "linddun", "kaynak_kimlik": "LINDDUN-I", "dil": "en",
     "baslik": "Identifiability",
     "metin": "An adversary is able to identify a data subject from a set of data subjects "
              "through an item of interest. Datasets described as anonymized often remain "
              "identifiable through quasi-identifiers such as timestamp, coarse location "
              "and device model in combination."},
    {"kaynak_turu": "linddun", "kaynak_kimlik": "LINDDUN-Dd", "dil": "en",
     "baslik": "Data disclosure",
     "metin": "Excessive or unnecessary personal data is collected, stored or shared "
              "relative to the stated purpose. Data minimization requires that each "
              "collected attribute be traceable to a specific processing purpose; "
              "attributes collected because they might be useful later fail this test."},
    {"kaynak_turu": "linddun", "kaynak_kimlik": "LINDDUN-U", "dil": "en",
     "baslik": "Unawareness and unintervenability",
     "metin": "The data subject is not aware of the collection or processing of their data, "
              "or cannot intervene in it. Third-party SDKs for analytics, crash reporting "
              "and advertising frequently transmit data without the data subject being "
              "informed, because the transmission is a side effect of including the library."},
    {"kaynak_turu": "linddun", "kaynak_kimlik": "LINDDUN-Nc", "dil": "en",
     "baslik": "Non-compliance",
     "metin": "The processing does not comply with legislation, regulation or the "
              "organization's own stated policy. Absence of a defined retention period, "
              "absence of a lawful basis for processing, and transfer to jurisdictions "
              "without an adequacy decision are typical instances."},

    # ------------------------------------------------------------ KVKK
    {"kaynak_turu": "kvkk", "kaynak_kimlik": "KVKK m.4", "dil": "tr",
     "baslik": "Genel ilkeler",
     "metin": "Kisisel veriler hukuka ve durustluk kurallarina uygun olarak islenir; "
              "dogru ve gerektiginde guncel olur; belirli, acik ve mesru amaclar icin "
              "islenir; islendikleri amacla baglantili, sinirli ve olculu olur; ilgili "
              "mevzuatta ongorulen veya islendikleri amac icin gerekli olan sure kadar "
              "muhafaza edilir. Amacla sinirlilik ilkesi, toplanan her veri alaninin "
              "belirli bir isleme amacina baglanabilmesini gerektirir."},
    {"kaynak_turu": "kvkk", "kaynak_kimlik": "KVKK m.5", "dil": "tr",
     "baslik": "Kisisel verilerin islenme sartlari",
     "metin": "Kisisel veriler ilgili kisinin acik rizasi olmaksizin islenemez. Kanunlarda "
              "acikca ongorulmesi, bir sozlesmenin kurulmasi veya ifasiyla dogrudan "
              "ilgili olmasi, veri sorumlusunun hukuki yukumlulugunu yerine getirebilmesi "
              "ve ilgili kisinin temel hak ve ozgurluklerine zarar vermemek kaydiyla mesru "
              "menfaat halleri acik riza aranmayan hukuki sebeplerdir."},
    {"kaynak_turu": "kvkk", "kaynak_kimlik": "KVKK m.6", "dil": "tr",
     "baslik": "Ozel nitelikli kisisel veriler",
     "metin": "Kisilerin irki, etnik kokeni, siyasi dusuncesi, felsefi inanci, dini, "
              "mezhebi veya diger inanclari, kilik ve kiyafeti, dernek, vakif ya da "
              "sendika uyeligi, saglig, cinsel hayati, ceza mahkumiyeti ve guvenlik "
              "tedbirleriyle ilgili verileri ile biyometrik ve genetik verileri ozel "
              "nitelikli kisisel veridir. Saglik ve cinsel hayat disindaki ozel nitelikli "
              "veriler kanunlarda ongorulen hallerde acik riza aranmaksizin islenebilir; "
              "saglik ve cinsel hayata iliskin veriler ise sir saklama yukumlulugu altinda "
              "bulunan kisiler veya yetkili kurum ve kuruluslar tarafindan islenebilir."},
    {"kaynak_turu": "kvkk", "kaynak_kimlik": "KVKK m.10", "dil": "tr",
     "baslik": "Veri sorumlusunun aydinlatma yukumlulugu",
     "metin": "Veri sorumlusu, kisisel verilerin elde edilmesi sirasinda ilgili kisilere "
              "kendisinin ve varsa temsilcisinin kimligi, kisisel verilerin hangi amacla "
              "islenecegi, islenen verilerin kimlere ve hangi amacla aktarilabilecegi, "
              "toplama yontemi ve hukuki sebebi ile ilgili kisinin haklari konusunda bilgi "
              "vermekle yukumludur."},
    {"kaynak_turu": "kvkk", "kaynak_kimlik": "KVKK m.12", "dil": "tr",
     "baslik": "Veri guvenligine iliskin yukumlulukler",
     "metin": "Veri sorumlusu, kisisel verilerin hukuka aykiri olarak islenmesini ve "
              "erisilmesini onlemek, muhafazasini saglamak amaciyla uygun guvenlik "
              "duzeyini temin etmeye yonelik gerekli her turlu teknik ve idari tedbiri "
              "almak zorundadir. Islenen verilerin kanuni olmayan yollarla baskalari "
              "tarafindan elde edilmesi halinde veri sorumlusu bu durumu ilgili kisiye ve "
              "Kurula bildirir."},
    {"kaynak_turu": "kvkk", "kaynak_kimlik": "KVKK m.9", "dil": "tr",
     "baslik": "Kisisel verilerin yurt disina aktarilmasi",
     "metin": "Kisisel veriler, ilgili kisinin acik rizasi olmaksizin yurt disina "
              "aktarilamaz. Yeterli korumanin bulundugu ulkelere aktarim veya yeterli "
              "korumayi yazili olarak taahhut eden veri sorumlulari ile Kurulun izninin "
              "bulunmasi halinde aktarim mumkundur. Bulut tabanli servislerin sunucu "
              "bolgesi bu acidan belirleyicidir."},

    # ------------------------------------------------------------ GDPR
    {"kaynak_turu": "gdpr", "kaynak_kimlik": "GDPR Art. 25", "dil": "en",
     "baslik": "Data protection by design and by default",
     "metin": "The controller shall implement appropriate technical and organisational "
              "measures, such as pseudonymisation, designed to implement data-protection "
              "principles in an effective manner. By default, only personal data which are "
              "necessary for each specific purpose of the processing are processed. This "
              "obligation applies at the time of determining the means of processing, "
              "which means at design time rather than after implementation."},
    {"kaynak_turu": "gdpr", "kaynak_kimlik": "GDPR Art. 28", "dil": "en",
     "baslik": "Processor obligations",
     "metin": "Where processing is carried out on behalf of a controller, the controller "
              "shall use only processors providing sufficient guarantees. Processing by a "
              "processor shall be governed by a contract setting out the subject matter, "
              "duration, nature and purpose of processing. Managed cloud services and "
              "third-party APIs that receive personal data are processors under this article."},
    {"kaynak_turu": "gdpr", "kaynak_kimlik": "GDPR Art. 32", "dil": "en",
     "baslik": "Security of processing",
     "metin": "The controller and processor shall implement appropriate technical measures "
              "including the pseudonymisation and encryption of personal data, the ability "
              "to ensure ongoing confidentiality, integrity and availability, and a process "
              "for regularly testing and evaluating the effectiveness of the measures."},

    # ------------------------------------------------------------ saglayici
    {"kaynak_turu": "saglayici", "kaynak_kimlik": "SAGLAYICI-firebase", "dil": "tr",
     "baslik": "Firebase veri isleme davranisi",
     "metin": "Firebase Realtime Database ve Firestore verileri Google altyapisinda "
              "barindirir. Veritabani ornegi olusturulurken secilen bolge verinin fiziksel "
              "konumunu belirler ve sonradan degistirilemez; varsayilan secim ABD "
              "bolgeleri olabilir. Erisim denetimi Firebase Security Rules ile yapilir; "
              "kurallar yapilandirilmadiginda test modu tum okuma ve yazma isteklerine "
              "acik olabilir. Firebase Analytics ve Crashlytics, uygulama SDK'si dahil "
              "edildiginde ayrica cihaz ve kullanim verisi toplar."},
    {"kaynak_turu": "saglayici", "kaynak_kimlik": "SAGLAYICI-llm-api", "dil": "tr",
     "baslik": "Barindirilan LLM API'lerinde istem verisi",
     "metin": "OpenAI, Anthropic ve Google Gemini gibi barindirilan model API'lerinde "
              "gonderilen istem ve alinan yanit saglayici sunucularinda islenir. Kurumsal "
              "planlarda egitim amacli kullanim varsayilan olarak kapali olabilir, ancak "
              "kotuye kullanim denetimi icin belirli bir sure saklama uygulanabilir. "
              "Istem icine kullanici kayitlari, hasta bilgileri veya kimlik verileri "
              "gomuluyorsa bu veriler de ayni yolu izler. Veri isleme sozlesmesi ve "
              "saklama suresi ayarlarinin kontrol edilmesi gerekir."},
    {"kaynak_turu": "saglayici", "kaynak_kimlik": "SAGLAYICI-nesne-depolama", "dil": "tr",
     "baslik": "Nesne depolama servislerinde erisim denetimi",
     "metin": "AWS S3, Google Cloud Storage ve Azure Blob Storage varsayilan olarak ozel "
              "erisimle olusturulur, ancak dosya paylasimini kolaylastirmak icin herkese "
              "acik okuma izni verilmesi yaygin bir yapilandirmadir. Bir kova herkese acik "
              "hale geldiginde icindeki tum nesneler dizinlenebilir ve arama motorlarinda "
              "gorunebilir. Imzali URL kullanimi, kova politikasi ve nesne duzeyi izinler "
              "kontrol edilmelidir."},
    {"kaynak_turu": "saglayici", "kaynak_kimlik": "SAGLAYICI-telemetri", "dil": "tr",
     "baslik": "Hata izleme ve analitik SDK davranisi",
     "metin": "Sentry, Crashlytics ve benzeri hata izleme araclari istisna aninda yigit "
              "izi ile birlikte istek govdesi, kullanici kimligi, cihaz bilgisi ve bazi "
              "yapilandirmalarda ortam degiskenlerini de gonderebilir. Google Analytics ve "
              "benzeri analitik SDK'lari cihaz tanimlayicisi ve kullanim olaylarini "
              "toplar. Bu aktarimlar kutuphane dahil edildigi anda baslar ve uygulama "
              "kodunda acikca gorunmez; veri kazima (data scrubbing) ayarlari ve toplanan "
              "alan listesi kontrol edilmelidir."},
    {"kaynak_turu": "saglayici", "kaynak_kimlik": "SAGLAYICI-push", "dil": "tr",
     "baslik": "Anlik bildirim servislerinde icerik",
     "metin": "Firebase Cloud Messaging ve Apple Push Notification servisi uzerinden "
              "gonderilen bildirim govdesi saglayici altyapisindan gecer. Bildirim "
              "metninde kisisel veri, saglik bilgisi veya islem detayi tasiniyorsa bu veri "
              "ucuncu tarafa aktarilmis olur. Bildirimlerde yalnizca tanimlayici olmayan "
              "bir uyari metni tasinip icerigin uygulama icinde cekilmesi yaygin bir "
              "azaltim yontemidir."},
]
