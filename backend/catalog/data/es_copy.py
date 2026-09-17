"""Spanish copy for catalogue text that was written in English, keyed by slug.

Written by hand, not machine translated: the site is only ever English and Spanish, and the jokes, club names and
nicknames do not survive an MT pass (it turned "open mic slots" into slot machines and renamed Trevy Tuesday).
Applied by `manage.py apply_es_copy`, which never overwrites Spanish typed into the admin unless asked.

Proper nouns stay in English: club names, show titles, awards, handles and people.
"""

ARTIST_BIOS = {
    'abi-sanchez': """Abi Sánchez es un comediante radicado en Chicago, conocido por su estilo relajado y observacional, que refleja su experiencia como latino en Estados Unidos.

Lleva años en la escena de comedia de Chicago y se ha presentado en clubes y festivales importantes de todo el país. Conduce shows mensuales como Pilsen Stand Up, encabeza carteles en clubes consagrados (Laugh Factory, Zanies, CG's Comedy Club) y ha tenido exposición nacional con Just For Laughs y HBO Latino.

Festivales y competencias:

Seleccionado para el festival Just For Laughs de Montreal y presentado en la LOL Network de Kevin Hart • Ganador del concurso de stand-up de HBO Latino (2020)

Medios y especiales:

• Aparece en HBO Max Latino.

• Participó en Tumbleweeds con Killer Mike (Hulu) y en contenido de Peacock, representando a la comedia de Chicago""",

    'adam-palmeter': """Adam Palmeter es un comediante estadounidense con una fuerte presencia en la escena internacional, sobre todo en Asia. Su humor ingenioso y su facilidad para conectar con públicos multiculturales lo han vuelto un favorito en países como China, Japón y Filipinas, además de Estados Unidos.""",

    'alyx-libby': """Alyx Libby es comediante de stand-up, actriz y fotógrafa radicada en Atlanta. Gira por todo el país como comediante profesional y además produce shows y entrena Muay Thai.""",

    'andrew-jonch': """El único hombre nacido en México, criado en México y llamado Andrew, carajo. Andrew Jonch es un comediante internacional conocido tanto en inglés como en español por sus shows en Norteamérica: Chicago, Nueva York, Miami, Ciudad de México, Cancún, Playa del Carmen y más allá. Como cofundador de Iguana Comedy, Andrew no es solo un tipo gracioso en México: es el responsable de traer comedia internacional al Caribe mexicano y de construir la escena en toda la Riviera Maya.""",

    'andre-de-freitas': """André De Freitas es un comediante premiado y aclamado por la crítica, conocido por su comedia personal y afilada y por su mirada global.

Se ha presentado en Europa, Estados Unidos, Dubái y Australia, donde ganó el Best International New Act en el Melbourne International Comedy Festival.

En 2023, su primer espectáculo solista, What If, se estrenó en el Edinburgh Fringe Festival con gran recepción: varias reseñas de cinco estrellas y un lugar en la lista de The Telegraph con los chistes más divertidos del Fringe. El especial completo salió en YouTube en junio de 2025.

Es cocreador y protagonista de Comedy Therapy, un show en vivo y podcast que mezcla humor y salud mental, que fue un éxito de taquilla y llegó al puesto número 3 de podcasts en Portugal. André suma más de 50 millones de reproducciones en redes.

Participó en el BBC World Service Arts Hour Comedy Special (2024) y antes coescribió y protagonizó una campaña global de Bybit junto a los campeones de Fórmula 1 Max Verstappen y Sergio "Checo" Pérez.

André nos acompaña en 2026 en su primera gira por México.""",

    'april-hirschman': """April Hirschman es comediante, conductora de podcast y coach de sexo e intimidad para parejas y para quien vaya solo. También es autora de libros sobre el deseo y las rupturas, y en el escenario hace stand-up sobre temas como la zona vinícola del condado de Sonoma, la bisexualidad y los corazones rotos.""",

    'brad-kofman': """Brad Kofman es un comediante, cineasta y músico premiado que encabeza carteles en clubes grandes como Laugh Factory y Zanies, obtuvo reconocimiento nacional en la competencia de Kenan Thompson y acumula un largo historial en festivales de cine, además de apariciones en televisión con Jeff Garlin. Su estilo es honesto y observacional: le entra a las inseguridades modernas y a las manías cotidianas con frescura y autenticidad.

Clubes habituales: comediante de planta en The Laugh Factory y Zanies Comedy Club de Chicago.

Se presenta con frecuencia en clubes de Chicago y Nueva York, muchas veces con varios sets por noche.

Ha actuado en The Comedy Store de La Jolla, California, como parte del showcase de Jeff Garlin You'll Probably Get Laid.

Premios y reconocimientos:

Finalista en la competencia nacional de comedia de Kenan Thompson (2019)

Cineasta premiado, con nueve cortometrajes exhibidos en más de 32 festivales y 19 reconocimientos, entre ellos en Cannes, Los Angeles International y Austin Film Festival

Medios y colaboraciones: Comediante invitado en You'll Probably Get Laid, el show de Jeff Garlin (Curb Your Enthusiasm) • Telonero y cartel compartido con Jeff Garlin en los shows de diciembre de 2024 en The Comedy Store • Elogiado por la prensa local por su mezcla de comedia pulida e improvisada con guitarra""",

    'captain-marina': """¡Ahoy, fans de la comedia! Como capitana con un cofre lleno de historias salvajes y divertidísimas, por fin eché el ancla y me subí al escenario. Años navegando en alta mar me dejaron una bodega repleta de anécdotas inolvidables y me emociona compartirlas. De lo absurdo a lo increíble, prepárate para zarpar conmigo en un viaje de pura carcajada.""",

    'chandler-jordana': """Un comediante estadounidense vuelto bilingüe, y ahora hasta le tira a latino con la pronunciación. Después de vivir varios años en Tijuana, Chandler es conocido por su perspectiva gringa en México, que le ha ganado un buen público en redes sociales.""",

    'charlie-albarrran': """Comediante. Empresario. Marihuano. Charlie es triple amenaza, amigo de Iguana Comedy, un comediante nuevo y prometedor en la escena, y un whitexican como no has visto otro.""",

    'danton-lamar': """Danton Lamar es comediante, escritor, productor, maestro y fundador de Comedy Lab, el único club de comedia de Canadá con dueños negros y queer. Tiene una presencia importante en redes sociales y se ha presentado en shows como Break Point Comedy.""",

    'easha-perinpanathan': """Youtuber. Comediante. Autora. Easha es triple amenaza, aunque está demasiado chiquita para amenazar a nadie.

Si viste su YouTube o leíste sus libros, sería lógico pensar que sus enseñanzas de "Amor Radical" le estorban en el stand-up, pero te equivocarías. Easha será pacifista, pero no tiene nada de pasiva la forma en que destroza un escenario.""",

    'fernanda-gutierrez': """Escribiendo chistes para las chicas y los gays, Fernanda Gutiérrez lleva años presentándose en inglés y en español, tanto aquí con Iguana como en shows internacionales en Tokio.""",

    'george-rigden': """George Ridgen es un comediante británico que lleva su estilo ingenioso y sarcástico a escenarios de todo el mundo. Con mirada europea y una voz muy suya, ofrece una lectura divertida de la vida moderna y la cultura global.""",

    'graham-elwood': """Graham Elwood es comediante, actor y cineasta, también conocido por su activismo político. Ha girado por el mundo entreteniendo a las tropas estadounidenses y ha coconducido podcasts populares como Comedy Film Nerds. Su estilo mezcla sátira social y política con historias personales.""",

    'harmony-mcelligott': """Harmony McElligott es comediante, actor y guionista nominado al Emmy por su trabajo en Robot Chicken. Hace stand-up, improvisación y sketch, y es egresado de The Groundlings Sunday Company en Los Ángeles. Como actor ha aparecido en HBO, Comedy Central, IFC y en muchos comerciales. Es conocido por los personajes y las imitaciones que mete en sus rutinas.""",

    'hector-ayala': """Radicado en Barcelona, Héctor Ayala destaca por su humor agudo y reflexivo. Mezcla su mirada latinoamericana con la vida europea para dar una lectura fresca de temas culturales, sociales y existenciales.""",

    'hector-q': """Hector Q es un comediante conocido por sus presentaciones en el Caribe mexicano. Ha mostrado su talento en línea a través de TikTok, con la cuenta @officialhectortv1, donde publica clips de comedia virales y sketches.""",

    'ivan-el-homie': """Residente de Cancún, inglés apenas entendible y homie de verdad. ¿Qué más se puede pedir?""",

    'joan-crowe': """¡La cantante de jazz más divertida de Nueva York! Joan es la creadora del podcast FunnyJazzChick.com, grabado en vivo en Birdland durante el Cast Party de Jim Caruso. También lidera una nueva banda llamada Jesters of Jive. Puedes ver a su banda de jump, jive y swing en: http://www.JestersofJive.com""",

    'jocelyn-chia': """Originaria de Singapur y radicada en Estados Unidos, Jocelyn Chia es conocida por su comedia atrevida, inteligente y a veces provocadora. Su material explora la identidad cultural y las diferencias generacionales. Ha ganado competencias de comedia y se ha presentado en los mejores foros de Nueva York.""",

    'joe-pettis': """Joe Pettis es un comediante estadounidense, pieza clave de la escena de comedia alternativa del sur de Estados Unidos. Creó el Underwear Comedy Party y se ha presentado en varios festivales del país. Su humor es irreverente, relajado y original.""",

    'jordan-cerminara': """Jordan Cerminara es comediante de stand-up y artista de collage radicado en Cancún. También es coproductor de The Art Critique Comedy Show, donde los comediantes analizan y subastan arte de bazar. Conocido por su creatividad y su estilo particular, siempre saca risas con sus presentaciones.""",

    'kai-nguyen': """Es vietnamita. Es judío. Fue broker de finanzas y ahora es comediante internacional, y te lo va a contar todo. Conocido por sus presentaciones en muchos países y por ser el primer comediante en Kill Tony: Kill or Be Killed de Netflix, Kai Nguyen es habitual de la escena de Playa y amigo cercano de Iguana Comedy.""",

    'keenan-steiner': """Keenan Steiner es un comediante conocido por su material sin temas prohibidos, su autenticidad y su vibra suelta. Se formó en Nueva York, se llevó su comedia a México durante tres años y luego regresó a NYC. Se ha presentado en el Edinburgh Fringe Festival, el New York Comedy Festival, el Red Clay Comedy Festival y muchos más. Ha contado chistes en HQ Trivia, en SiriusXM y en TIME. De 2021 a 2023 se soltó en México, donde estrenó su primera hora de stand-up en inglés y pronto empezó a hacer stand-up en español, que no es su lengua materna. En total ha presentado su hora, Sneaky, y otra distinta en español, decenas de veces en ciudades de México y en Nueva York.""",

    'liam-slater-1': """Inteligente. Gracioso. Inglés. Solo una de esas tres cosas es cierta.

Liam es un comediante sarcástico con una visión pesimista del mundo que decidió que la vida es mejor si te ríes de ella. Como uno de los cofundadores de Iguana Comedy, cuando veas a un whitexican riéndose, piensa en Liam.

Después de presentarse en clubes de comedia de Edimburgo y de México, Liam se hizo de un nombre siguiendo los pasos de sus ancestros coloniales: el inglés al que nadie invitó, pero que de todos modos sigue viniendo.""",

    'liz-derr': """Liz Derr es una comediante de stand-up conocida por su humor negro y por hablar de temas pesados. Vive en Atlanta y también destaca como actriz, sobre todo en la película Blood Mountain Massacre.""",

    'matt-mclean': """Matt es un comediante que vive en su camioneta y pasa la mayor parte del tiempo en el bosque. Vuelve a la ciudad solo para contarle chistes a la gente cool (sí, tú). Nacido en Minnesota y con formación de ingeniero, su comedia es nerd pero cercana: mezcla observaciones agudas con autoburla juguetona. Engancha al público rápido y lo mantiene riendo toda la noche. Míralo pronto, antes de que el bosque se lo quede para siempre. Después de vivir en Chicago y presentarse en Zanies, Laugh Factory, Comedy Bar y la Madison Comedy Week, Matt pasó una temporada en Carolina del Norte, donde fue habitual en Goodnight's y Dead Crow. Hoy se presenta en clubes de todo Estados Unidos y ha abierto para comediantes como Luke Null, Tim Butterly y Eagle Witt.""",

    'noah-miller': """Noah Miller es comediante y guionista radicado en Nueva York. Después de once años como piloto de helicóptero en la Guardia Costera, hizo la transición natural a la comedia y no ha mirado atrás.""",

    'oumer-isha': """Un "runaholic" en recuperación. Oumer es un comediante viajero de primer nivel que se ha presentado en casi todos los continentes: de día inventa ideas de alta tecnología y de noche inventa chistes de baja estofa.""",

    'pat-degeest': """Pat DeGeest empezó su carrera en la comedia en 2020 en Key West, donde se enamoró del oficio de inmediato. Conocido por sus giros inesperados, su humor negro y su forma de jugar con el público, Pat ha entretenido a todo tipo de audiencias en Estados Unidos. Con un encanto que te hace reír en un momento y cuestionar la realidad al siguiente, se volvió rápido un favorito del público y de los comediantes.""",

    'rahul-nimmagadda': """Rahul es un comediante indio-estadounidense que le entra al amor, la familia y la fe con chistes que van del juego de palabras ingenioso al tabú que te deja con la boca abierta. Es íntimo, temerario y graciosísimo: viene a hablar de encontrarse a uno mismo perdiéndose en todas las personas equivocadas.""",

    'renee-percy': """Renee Percy es una comediante, actriz y escritora premiada de Canadá. Con una carrera amplia en televisión y en stand-up, su estilo combina inteligencia, sátira y relato personal. Ha trabajado con nombres importantes del entretenimiento y ha sido reconocida por su escritura de comedia.

Stand-up y shows en vivo:

• Giras extensas por Estados Unidos y Canadá, encabezando los clubes Yuk Yuk's

• Participación en el festival Netflix Is a Joke

• Se presenta en los mejores foros: The Laugh Factory, The Comedy Store, The Improv, Flappers Comedy Club y The Comedy & Magic Club

Televisión y escritura de sketch:

• Actriz regular y guionista de planta en Comedy Inc. (CTV/Comedy Network, 2003 a 2007)

• Única mujer guionista de planta en Air Farce Live (CBC).

• Apareció en el especial Comedy Now! Women of the Night II

• Apariciones invitadas en series de cadenas estadounidenses: Mom, Superstore, The Goldbergs, Workaholics, The Thundermans, Jimmy Kimmel Live y más.

• Creó y estrenó su propio especial de stand-up, The Komic Sutra, disponible en Amazon Prime y Apple TV, que debutó como el álbum de comedia número 1 en iTunes

Giras y teloneos: Ha abierto para figuras como Jay Leno, Jeff Garlin, Craig Robinson, Preacher Lawson, Jamie Kennedy, Orny Adams, Michael Rapaport y Yakov Smirnoff, y fue acto invitado de Arsenio Hall""",

    'rodrigo-sagastegui': """Comediante mexicano bilingüe radicado actualmente en Querétaro. Antes fue parte fundamental de la comunidad internacional de Playa del Carmen por más de una década. Eso, claro, siempre le da material de sobra, con la mirada de alguien local y de alguien que ayudó a recibir a los recién llegados a México.

Siempre trae buenos chistes y buena gente a tus shows.""",

    'sandy-bernstein': """Sandy Bernstein es una comediante de stand-up radicada en Baltimore y Washington que atrapa al público con su humor autoburlón y su manera animada de contar historias. Es la tía cool que te hubiera gustado tener.

Sandy es amiga de Iguana y se ha presentado con nosotros muchas veces.""",

    'sive-juarez-bourke': """Sive (Sadhbh Juárez Bourke) es una comediante hispano-irlandesa recién importada desde Alemania. Se presenta en inglés y en español, y su comedia trata sobre todo de ser humano y no hacerlo particularmente bien. Le gusta hacerte sentir en confianza, hasta que dejas de estarlo.""",

    'sunflower-julie': """Criada en Ucrania y radicada hoy en Estados Unidos, Sunflower Julie es habitual de nuestros shows y se ha presentado en clubes de comedia de Nueva York, Nueva Jersey, Washington y Playa del Carmen.""",

    'tito-jorda': """El comediante Tito Jorda-Cid tuvo un 2023 destacado: se coronó campeón de Roast Battle Chicago y se presentó en The Mothership, en Austin. También es conocido por sus apariciones en podcasts y shows de roast del circuito.""",

    'tom-rhodes': """Comediante veterano, Tom Rhodes es una leyenda del circuito internacional. Se ha presentado por todo el mundo, incluidos Europa, Asia y Sudamérica, y es conocido por su humor filosófico, humanista e inspirado en los viajes. Ha conducido especiales para Comedy Central y otras cadenas importantes.""",

    'tori-morancay': """Comediante nacida en Francia que hoy se presenta por Nueva York, ¡y que nos visitó para un show tropical muy divertido en 2024!""",

    'tory-ward': """Comediante radicada en Chicago, Tory Ward se hizo de un nombre con su ingenio veloz y su estilo directo. Habitual de los mejores clubes de la ciudad, ha estado en festivales y podcasts, y se ha ganado el reconocimiento por su voz auténtica y divertidísima. Con una presencia fuerte en Chicago y también en la escena de Portland, donde empezó, Tory es amiga cercana de Iguana y su especial Shine in the Dark se estrena pronto.""",

    'trevor-green': """Amigo de Iguana Comedy desde hace años, Trevor Green es muchas cosas. Dueño de Campfire Comedy en Thunder Bay, Canadá. Visitante frecuente de Quintana Roo. Técnicamente mexicano. Y logra que el autismo y el pelo rojo se vean adorables.""",

    'turner-sparks': """Originario de California y radicado en Nueva York, Turner Sparks empezó su carrera en la comedia en China, donde fundó una de las primeras compañías de comedia en inglés del país. Con una mirada global, Turner mezcla experiencia internacional con humor clásico estadounidense, y coconduce un podcast popular de cultura y comedia.""",

    'wardie-leppan': """Wardie Leppan es sudafricano de origen, pero huyó a Canadá durante el Apartheid.

Un señor mayor con un humor que no corresponde a sus años, Wardie le ve el lado divertido a envejecer y está decidido a no hacerlo con elegancia.

Puedes verlo seguido en Ottawa, y en 2026 nos acompañó en un show privado.""",

    'what-the-hell-amy': """Amy López es una maestra joven y muy querida de español e inglés, de Playa del Carmen, que presume su humor negro y filoso. Este año se mudó a Europa, donde sigue subiéndose a escenarios de comedia.

Amy es amiga cercana de Iguana y parte esencial de la escena de comedia de Playa.""",

    'zach-mcgovern': """Comediante y coproductor de @poppycomedy, Zach es un comediante radicado en Nueva York que se presenta por toda la zona en lugares como New York Comedy Club y The Stand. Entre sus créditos hay una aparición en MTV, un especial de OnlyFans (no de ese tipo, saca la mente del arroyo) y muchos más.""",

    'zia-durrani': """¿Afgano? ¿Estadounidense? ¿Mexicano? Nadie sabe bien. Lo que sí sabemos es que Zia vive en México la mayor parte del tiempo, es amigo de Iguana Comedy desde hace años y tiene un talento especial para que salgas del show riéndote muchísimo y con ganas de bañarte al mismo tiempo.""",
}

# The open mic series and the secret shows reuse one blurb across many dates, so the Spanish is written once here.
OPEN_MIC_BODY = """Va a ser divertido.

Va a ser raro.

A veces va a ser una porquería.

Pero esa es la belleza de un open mic.

Reserva tu boleto y, si te subes al escenario y haces 5 minutos, te devolvemos el boleto y te damos una cerveza gratis para celebrar tu éxito (esperemos).

No tenemos muchos lugares, se va a llenar.

¡Reserva ya!"""

EUROTRIP = {
    'description': '¡Los europeos volvieron! ¡Pero esta vez para bien!',
    'long_description': """¡Los europeos volvieron! ¡Pero esta vez para bien!

Después de reventar escenarios en Portugal, Londres y Nueva York, André de Freitas nos acompaña en su primera gira por México.

André es divertido, bilingüe, rapidísimo y con la esperanza de descubrir cuántos de sus 150 mil seguidores de Instagram viven en la península de Yucatán (¡crucen los dedos!).

Best International New Act en el Melbourne International Comedy Festival, aplausos de la crítica por su primera hora solista, What If, en el Edinburgh Fringe Festival, más de 50 millones de reproducciones en redes y apariciones en campañas publicitarias junto a los campeones de Fórmula 1 Max Verstappen y Sergio "Checo" Pérez: André es una estrella en ascenso y nos da mucho gusto tenerlo en México.

Junto con André vas a ver a otros dos comediantes europeos. Sive se presenta por primera vez en México. Comediante hispano-irlandesa-alemana (vaya combinación), sabe decir su verdad y hacerla graciosa aunque nadie más se identifique. Y te recibe el cofundador de Iguana Comedy, el muy británico Liam Slater. Divertido, rápido, encantador (él me obligó a escribir eso), Liam trae una mirada muy suya a la experiencia del "güero en México" y quiere contarte lo que piensa.""",
}

SECRET_SHOW = {
    'description': '¡Shhhh! Nos emociona mucho traerte un show secreto en el corazón de {city}.',
    'long_description': """¡Shhhh!

Nos emociona mucho traerte un show secreto en el corazón de {city}.

¿El ambiente?
Increíble.

¿La ubicación?

Se revela 24 horas antes del evento.

¿Deberíamos estar haciendo un show ahí?

Para nada.

Acércate y ve la comedia en su estado más crudo. Poca gente, sin escenario, sin reglas.{extra}

Pero hagas lo que hagas:

Shhhhh.""",
}

EVENT_COPY = {
    'cancun-2025-09-20': {
        'description': '¡El primer open mic de stand-up en inglés en Cancún!',
        'long_description': '¡El primer open mic de stand-up en inglés en Cancún!\n\n' + OPEN_MIC_BODY,
    },
    'cancun-open-mic-cancun': {
        'description': 'En plena temporada de huracanes, nuestro segundo open mic regresa a Cancún (sabemos elegir las fechas)',
        'long_description': ('En plena temporada de huracanes, nuestro segundo open mic regresa a Cancún '
                             '(sabemos elegir las fechas)\n\n' + OPEN_MIC_BODY),
    },
    'playa-del-carmen-2025-09-25': {
        'description': '¡Justo cuando empieza la temporada de huracanes, los open mics vuelven a Playa! (sabemos elegir las fechas)',
        'long_description': ('¡Justo cuando empieza la temporada de huracanes, los open mics vuelven a Playa! '
                             '(sabemos elegir las fechas)\n\n' + OPEN_MIC_BODY),
    },
    'playa-open-mic-playa-del-carmen': {
        'description': '¡En plena temporada de huracanes volvemos con otro open mic en Playa! (sabemos elegir las fechas)',
        'long_description': ('¡En plena temporada de huracanes volvemos con otro open mic en Playa! '
                             '(sabemos elegir las fechas)\n\n' + OPEN_MIC_BODY),
    },
    'playa-open-mic-english': {
        'description': '¡Bienvenido de vuelta al open mic en inglés de Playa!',
        'long_description': """¡Bienvenido de vuelta al open mic en inglés de Playa!

Tenemos un montón de comediantes locales e internacionales viniendo a probar material, además de lugares reservados para quienes empiezan. Esperamos diversión, esperamos risas.

¡Te recibe el comediante mexicano bilingüe Charlie Albarran!

Ven, toma algo, ríete y, si te sientes valiente, súbete al escenario y enséñanos tus 5 minutos.""",
    },
    'playa-open-mic-espanol': {
        'description': '¡Bienvenido al open mic de Los ChiLaughOs!',
        'long_description': """¡Bienvenido al open mic de Los ChiLaughOs!

Tenemos un montón de comediantes locales e internacionales viniendo a probar material, además de lugares reservados para quienes empiezan. Esperamos diversión, esperamos risas.

Presentado por nuestro anfitrión local Charlie Albarran, la pasas bien garantizado.

Ven, toma algo, ríete y, si te sientes valiente, súbete al escenario y enséñanos tus 5 minutos.""",
    },
    'cozumel-comedy-august-cozumel': {
        'description': '¡El stand-up vuelve a Cozumel! Iguana Comedy regresa a traer las risas a la isla, en inglés.',
        'long_description': """¡El stand-up vuelve a Cozumel! Iguana Comedy regresa a traer las risas a la isla, en inglés.

¡Esta vez son 2 noches, el doble de risas y el doble de diversión!

Viernes 8 y sábado 9 de agosto.

Función a las 8:00 pm

Con un cartel de comediantes internacionales:

Fernanda Gutierrez, Playa del Carmen, México

Andrew Jonch, Cancún, México

Will Slater, Londres, Inglaterra

Captain Marina, algún lugar de Rusia

Solo en: Señor and the Queen. Calle 4 y Av. Rafael Melgar.""",
    },
    'dude-where-s-my-van-matt-maclean-teatro-xbalamque': {
        'description': 'Esta va a ser una noche especial.',
        'long_description': """Esta va a ser una noche especial.

Por primera vez en Quintana Roo, volando desde "donde sea que haya estacionado su camioneta la última vez", Matt MacLean.

Matt es un comediante de primer nivel, parte fundamental de la escena de Chicago, y hay quien jura que es hombre lobo por el pelo, la barba y su costumbre de desaparecer en el bosque sin avisar.

Logramos atraparlo y sacarlo del bosque para traerlo a una pequeña gira por nuestros lugares favoritos de la península.

Lo han descrito como nerd, cercano, de ingenio rápido y "vive en su camioneta", pero sobre todo es un comediante enorme, gran amigo de Iguana Comedy y garantía de alegrarte el día con su marca McLean de comedia.

Junto a Matt vas a ver al showrunner y cofundador de Iguana Comedy, Andrew Jonch. Con shows en muchos países, carretera encima y tres idiomas que usa para hacerte reír en todos, Andrew es un asesino que convierte a un Mexicant en mexicano.

También vas a conocer a nuestro telonero y novato de la comedia Charlie Albarran, híbrido mexicano-estadounidense que no tiene miedo de irse un poquito demasiado oscuro, y te recibe la otra mitad de Iguana Comedy, Liam Slater, comediante británico de humor seco, debilidad por lo ridículo y siempre dispuesto a preguntar "¿qué chingados está pasando?".

Van a ser 4 comediantes internacionales en un show que no te vas a querer perder.

Esperamos llenar, así que ahora es el momento de comprar tus boletos.""",
    },
    'new-york-invasion-cancun': {
        'description': ('¡Nueva York llega a Cancún! Dos comediantes profesionales de la gran manzana traen comedia '
                        'de calidad a Cancún (el Big Taco) por una sola noche y en una sola ciudad.'),
        'long_description': """¡Nueva York llega a Cancún! Dos comediantes profesionales de la gran manzana traen comedia de calidad a Cancún (el Big Taco) por una sola noche y en una sola ciudad. No te lo pierdas.

Zach Mcgovern es un comediante radicado en Nueva York cuyo estilo sarcástico y un poco filoso lo tiene sonando cada vez más en la escena.

Noah Miller es un expiloto de helicóptero de la Guardia Costera que lo dejó todo por perseguir su sueño de hacer stand-up, una transición de lo más natural. Es ingenioso, rápido y una estrella en ascenso en la escena neoyorquina.

Zia Durrani, nuestro afganimexamericano local y exresidente de Nueva York, se sube al escenario a recordar su época en la ciudad y lo que más extraña (las ratas, seguramente).

Y el único no neoyorquino de la noche es tu anfitrión, Trevor Green. Canadiense sin duda, técnicamente mexicano (pregúntale cómo pasó eso) y dueño de su propio club de comedia en Thunder Bay, Canadá. Trevor es amigo de Iguana desde hace años, graciosísimo, y seguro te hace reír y sentir pena ajena al mismo tiempo.""",
    },
    'payday-punchline-puerto-morelos-puerto-morelos': {
        'description': '¡Puerto! Ustedes pidieron y nosotros respondimos.',
        'long_description': """¡Puerto! Ustedes pidieron y nosotros respondimos. Un show sorpresa con dos comediantes profesionales que tenemos en la ciudad. Cupo limitado, ¡solo para ustedes!

Vas a ver a Matt Maclean, comediante profesional radicado en Minnesota, en su última fecha en Quintana Roo (después de llenar Cancún, Playa, Tulum y Cozumel).

Vas a ver a Rahul Nimmagadda, comediante indio-estadounidense de Filadelfia que hoy vive y trabaja en la Ciudad de México.

Y claro, vas a ver a comediantes locales, con el cofundador de Iguana, Andrew Jonch, como anfitrión.""",
    },
    'rooftop-secret': {
        'description': '¡Shhhh!',
        'long_description': """¡Shhhh!

Nos emociona mucho traerte un show secreto en el corazón de Playa del Carmen.

¿El ambiente?
Increíble.

¿La ubicación?

Se revela 24 horas antes del evento.

¿Deberíamos estar haciendo un show ahí?

Para nada.

Acércate y ve la comedia en su estado más crudo. Poca gente, sin escenario, sin reglas.

La última vez llenamos mucho antes de la fecha y no esperamos que esta sea distinta, así que te recomendamos reservar ya.

Pero hagas lo que hagas:

Shhhhh.""",
    },
    'shhhh-secret-shows-august': {
        'description': '¡Shhhh! Nos emociona mucho traerte un show secreto en el corazón de Cancún.',
        'long_description': SECRET_SHOW['long_description'].format(city='Cancún', extra=''),
    },
    'shhhh-secret-show-shhhh': {
        'description': '¡Llegamos con nuestro primer show secreto en Puerto Aventuras!',
        'long_description': """¡Llegamos con nuestro primer show secreto en Puerto Aventuras!

Una ubicación secreta, que se anuncia 24 horas antes.

¿Deberíamos estar haciendo un show ahí?

Para nada.

Llevamos 6 shows seguidos llenos y aquí el cupo es limitado, así que no esperamos otra cosa.

Es nuestra primera vez en Puerto Aventuras, así que este show no te lo vas a querer perder.

Emociónate, reserva ya, pero hagas lo que hagas:

¡Shhhhhhh!""",
    },
    'shhh-secret-show-shhhh': {
        'description': 'Estamos reinventando nuestros shows secretos y llevándolos aún más al underground.',
        'long_description': """Estamos reinventando nuestros shows secretos y llevándolos aún más al underground.

Esto es mitad show, mitad taller. Vas a ver a los comediantes en su estado más crudo: a veces vas a escuchar chistes nuevos antes que nadie, a veces vas a verlos fallar y ese chiste no se va a contar nunca más.

Cuando termine, vamos a beber, fumar y platicar del show.

Sin boletos, sin cámaras, una ubicación secreta en casa de alguien y la oportunidad de ver a la gente afinar su oficio en tiempo real.

Estos shows tienen cupo muy limitado (para este habrá solo 10 lugares) y son por invitación. ¿La página en la que estás ahora? No se puede llegar a ella desde el sitio de Iguana. Si estás aquí es porque alguien te pasó el dato. ¿Fue un comediante amigo tuyo? Dinos quién, ese es tu boleto de entrada. ¿Te enteraste de otra forma? Anótate en la lista de espera aquí abajo y te avisamos cuando se abra un lugar.""",
    },
    'runnin-outta-time-oumer-isha-bipolar': {
        'description': 'Se describe como un "runaholic en recuperación": Oumer se ha presentado en todos los continentes.',
        'long_description': """Se describe como un "runaholic en recuperación": Oumer se ha presentado en todos los continentes.

De día inventa ideas de alta tecnología y de noche suelta chistes enormes. De tanto viajar, es buenísimo para traer al escenario una mirada aguda, mundana y graciosamente cercana.

Ah, pero hay más.

Como esta gira se extiende hasta el año nuevo, vas a ver una rotación de comediantes según la fecha.

En Cancún y Playa nos emociona mucho tener en el escenario a nuestro anfitrión y cofundador de Iguana Comedy, Andrew Jonch.

Lo acompaña un invitado especial desde Estados Unidos. ¿Te has preguntado qué hacen los artistas del collage cuando no están creando? Resulta que hacen comedia. Jordan Cerminara trae creatividad y caos en un estilo distinto al que estamos acostumbrados, va a estar divertido.

En Tulum y Mérida vas a ver el regreso del "técnicamente mexicano" Trevor Green, comediante canadiense de Thunder Bay que vuelve triunfante a Quintana Roo después de abrir su club en Canadá, además de apariciones de otros amigos locales de Iguana Comedy.""",
    },
    'russian-comedy-cancun': {
        'description': 'Por primera vez, comedia rusa profesional en Cancún.',
        'long_description': """Por primera vez, comedia rusa profesional en Cancún.

Впервые в Канкуне.

Русскоязычный Стендап Концерт.

Специально приглашенные самые смешные комики Сиетла:

Ксюша Элькун

Артем Хандро

Женя Дос

Комикесса из Плая Дель Кармен:

Капитан Бриса

28 Ноября в 19.00

Театр Centro Cultural Xbalamqué

https://maps.app.goo.gl/Jo9wgWtMGHJrgwPM7

Билеты""",
    },
    'st-paddys-day-comedy-playa-del-carmen': {
        'description': ('Con unos cuantos chistes escritos, un par de lugares de open mic y la suerte de los '
                        'irlandeses, esperamos que ahora que baja la temporada podamos seguir los pasos de San '
                        'Patricio y sacar a todas las serpientes (canadienses) de Irlanda (México), al menos hasta '
                        'que regresen en 6 meses.'),
        'long_description': """Con unos cuantos chistes escritos, un par de lugares de open mic y la suerte de los irlandeses, esperamos que ahora que baja la temporada podamos seguir los pasos de San Patricio y sacar a todas las serpientes (canadienses) de Irlanda (México), al menos hasta que regresen en 6 meses.

Con comediantes de 5 países distintos sabemos que la vamos a pasar bien y, en el espíritu de la fiesta, todos pensamos estar bien borrachos. ¡Vente con nosotros!""",
    },
    'the-roast-of-hector-q-playa-del-carmen': {
        'description': ('Nuestro querido amigo Hector Q se va de Playa para siempre y, para recordarlo, decidimos '
                        'despedirlo con algo que lleva mucho tiempo queriendo. Un roast.'),
        'long_description': """Nuestro querido amigo Hector Q se va de Playa para siempre y, para recordarlo, decidimos despedirlo con algo que lleva mucho tiempo queriendo. Un roast.

Con roasts de Captain Marina, Andrew Jonch, Will Slater, Fernanda Gutierrez y el hombre del momento, el propio Hector, va a ser una noche divertida, cruel y capaz de terminar amistades.""",
    },
    'the-spooky-show-halloween-comedy-playa-del-carmen': {
        'description': '¡Es temporada de sustos!',
        'long_description': """¡Es temporada de sustos!

Cada año celebramos... ¿fantasmas o algo así? ¿disfrazándonos de puteque y poniéndonos hasta atrás?

Debe haber una historia real detrás de esto. Da igual.

Vamos a celebrar Halloween a nuestra manera, contando historias de miedo divertidas sobre cosas bien jodidas.

Y lo hacemos lo suficientemente temprano para que después todavía te puedas poner bien pedo.

4 comediantes contando historias (un poco) de miedo y (muy) divertidas.

¿Qué más quieres?

El fundador de Iguana, Andrew Jonch, viene a contarnos de aquella vez que se peleó con la ley y ganó la ley (porque es la policía mexicana, obvio).

Captain Marina regresa a contarnos cómo fue crecer en Rusia con la KGB.

¡Charlie Albarran llega con un set sorpresa en su primer show de verdad en Playa del Carmen!

Liam Slater es el anfitrión y viene a responder la pregunta "¿qué pasa cuando intentas robarle a un narcomenudista británico?" (seguro le fue de maravilla).

Buena comedia, buen tema, buenas bebidas, buen lugar.

Va a ser una gran noche.""",
    },
    'trevy-tuesday-july-2026': {
        'description': 'Trabaja de maneras misteriosas. Te ve tal como eres.',
        'long_description': """Trabaja de maneras misteriosas. Te ve tal como eres. Es residente mexicano sin hablar una palabra de español. Todo esto es cierto y a la vez completamente inexplicable.

Trevy Tuesday nos acompaña una sola noche para que busques dentro de ti y te hagas las preguntas importantes:

¿quién soy?
¿Qué es real?
¿Por qué chingados compré boletos para esto?

Todo será revelado.""",
    },
    'whacky-comedy-cancun': {
        'description': 'Solo se nos ocurre describirlo como "whacky". Nos vas a tener que creer.',
        'long_description': """Solo se nos ocurre describirlo como "whacky". Nos vas a tener que creer.

Trevor Green cuenta cómo consiguió la residencia mexicana sin ningún vínculo con México y sin hablar una palabra de español (pista: hubo mordida), George Ridgen nos canta canciones sobre la cultura de su tierra natal (Harry Potter) y los de siempre regresan, aunque les seguimos diciendo que no. Va a ser una buena noche, seguro.""",
    },
    'whacky-comedy-cozumel-cozumel': {
        'description': '¡Regresamos a Cozumel!',
        'long_description': """¡Regresamos a Cozumel!

Con 4 comediantes internacionales, gente rara y un tipo con una guitarra, va a estar de locos.""",
    },
}

# The Eurotrip run shares one blurb across every city and date.
for _slug in ('andr-de-freitas-eurotrip-cancun', 'andr-de-freitas-eurotrip-cozumel', 'andre-de-freitas',
              'andre-de-freitas-eurotrip-playa-del-carmen', 'cancun-2026-02-20', 'cancun-2026-02-20-1900',
              'merida-2026-02-27-1900', 'merida-2026-02-27-1900-73hs', 'merida-2026-02-27-1900-8cet',
              'merida-2026-02-27-1900-n5k1'):
    EVENT_COPY[_slug] = dict(EUROTRIP)
