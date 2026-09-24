"""English and Spanish for everything a customer sees from the backend: checkout, order page, emails and errors.

The English text is both the key and the fallback. `api.tests.TranslationTests` scans the code for every string that
goes through `tr()`, `{% t %}` or `CheckoutError(...)` and fails when one has no Spanish here, or when a Spanish entry
drops or adds a slot, so a customer-facing string cannot ship untranslated. Slots are positional (`{0}`) so a Spanish
sentence can reorder them.
"""

from urllib.parse import urlparse

ES = {
    # Checkout
    'Tickets': 'Boletos',
    'Tickets · {0}': 'Boletos · {0}',
    'Checkout needs JavaScript enabled.': 'Para comprar necesitas activar JavaScript.',
    'Member pricing applied.': 'Se aplicó el precio de socio.',
    'Full name': 'Nombre completo',
    'Email': 'Correo electrónico',
    'Phone (optional)': 'Teléfono (opcional)',
    'Choose how many with +': 'Elige cuántos con +',
    'Up to {0} per order': 'Máximo {0} por orden',
    'Reserve 1 seat': 'Reservar 1 lugar',
    'Reserve {0} seats': 'Reservar {0} lugares',
    'Pay {0} at the door': 'Pagas {0} en la puerta',
    'Free': 'Gratis',
    'Get 1 ticket': 'Obtener 1 boleto',
    'Get {0} tickets': 'Obtener {0} boletos',
    'Pay {0}': 'Pagar {0}',
    '1 ticket': '1 boleto',
    '{0} tickets': '{0} boletos',
    'Reserving...': 'Reservando...',
    'Processing...': 'Procesando...',
    'The total is now {0}. Press the button again to pay it.':
        'El total ahora es {0}. Vuelve a presionar el botón para pagarlo.',
    'Tickets are not on sale for this show.': 'Los boletos para este show no están a la venta.',
    'Local development: Stripe keys are not configured, so this button simulates a successful payment.':
        'Desarrollo local: Stripe no está configurado, así que este botón simula un pago exitoso.',
    'Sold out': 'Agotado',
    'pay at the door': 'pagas en la puerta',
    'members only': 'solo socios',
    '{0} left': 'quedan {0}',
    'Add one {0}': 'Agregar uno: {0}',
    'Remove one {0}': 'Quitar uno: {0}',
    'Member benefit ({0} free)': 'Beneficio de socio ({0} gratis)',
    'Member discount': 'Descuento de socio',
    'Something went wrong.': 'Algo salió mal.',

    # Checkout errors
    'Invalid request': 'Solicitud no válida.',
    'Invalid ticket selection': 'La selección de boletos no es válida.',
    'Enter your name and email.': 'Escribe tu nombre y tu correo electrónico.',
    'Online payment is not available yet. Please contact us to book.':
        'El pago en línea aún no está disponible. Contáctanos para reservar.',
    'Payment has not completed yet.': 'El pago aún no se ha completado.',
    'That ticket type is no longer available.': 'Ese tipo de boleto ya no está disponible.',
    'Choose between 0 and 20 tickets.': 'Elige entre 0 y 20 boletos.',
    'You can book up to {0} {1} per order.': 'Puedes reservar hasta {0} de «{1}» por orden.',
    '{0} is for members only.': '«{0}» es solo para socios.',
    '{0} is not available to members.': '«{0}» no está disponible para socios.',
    'Only {0} {1} tickets left.': 'Solo quedan {0} de «{1}».',
    '{0} is sold out.': '«{0}» está agotado.',
    'Choose at least one ticket.': 'Elige al menos un boleto.',
    'Reserve pay-at-the-door seats in their own order.': 'Reserva los lugares que se pagan en la puerta en una orden aparte.',
    'Only {0} {1} left.': 'Solo quedan {0} de «{1}».',
    '{0} is fully booked.': '«{0}» ya está lleno.',
    'You already have a reservation for this night. Check your email for your seats.':
        'Ya tienes una reservación para esta noche. Revisa tu correo para ver tus lugares.',

    # Order page
    'Your tickets': 'Tus boletos',
    'Your seats': 'Tus lugares',
    'Your tickets · {0}': 'Tus boletos · {0}',
    'doors {0}': 'puertas {0}',
    'show {0}': 'show {0}',
    'This order is {0}. Tickets appear here once payment completes.':
        'Esta orden está {0}. Los boletos aparecen aquí cuando se complete el pago.',
    'Booked by {0}. Show the code for each ticket at the door.':
        'Reservado por {0}. Muestra el código de cada boleto en la puerta.',
    'Pay {0} at the door.': 'Paga {0} en la puerta.',
    'Your seats are reserved. Nothing was charged online.': 'Tus lugares están reservados. No se cobró nada en línea.',
    'Ticket {0} of {1}': 'Boleto {0} de {1}',
    'Checked in': 'Registrado',
    'Check-in code': 'Código de registro',
    'Back to Iguana Comedy': 'Volver a Iguana Comedy',
    'pending': 'pendiente',
    'completed': 'completada',
    'refunded': 'reembolsada',
    'cancelled': 'cancelada',

    # Confirmation email
    'Hi {0},': 'Hola, {0}:',
    'Hi there,': 'Hola:',
    'You are booked for {0} on {1}.': 'Tu lugar para {0} el {1} está confirmado.',
    'You are booked for {0}.': 'Tu lugar para {0} está confirmado.',
    'Doors {0} · Show {1}': 'Puertas {0} · Show {1}',
    'Show {0}': 'Show {0}',
    'Venue: {0}': 'Lugar: {0}',
    'Pay {0} at the door for your seat. Nothing was charged online.':
        'Paga {0} en la puerta por tu lugar. No se cobró nada en línea.',
    'Pay {0} at the door for your {1} seats. Nothing was charged online.':
        'Paga {0} en la puerta por tus {1} lugares. No se cobró nada en línea.',
    'Your seats (show this at the door): {0}': 'Tus lugares (muéstralo en la puerta): {0}',
    'Your tickets (show this at the door): {0}': 'Tus boletos (muéstralo en la puerta): {0}',
    'See you there,': '¡Nos vemos ahí!',
    'Your reservation: {0}': 'Tu reservación: {0}',
    'Your tickets: {0}': 'Tus boletos: {0}',

    # Sign-in email
    'Sign in to Iguana Comedy:': 'Inicia sesión en Iguana Comedy:',
    'Or enter this code: {0}': 'O escribe este código: {0}',
    'The link and code expire in 30 minutes. If you did not ask for this, ignore this email.':
        'El enlace y el código vencen en 30 minutos. Si no lo pediste, ignora este correo.',
    'Your Iguana Comedy sign-in code: {0}': 'Tu código para iniciar sesión en Iguana Comedy: {0}',

    # API errors the site shows as-is (translated by api.middleware.TranslateErrorsMiddleware)
    'A valid email is required': 'Se requiere un correo electrónico válido.',
    'Billing is not available for this account': 'La facturación no está disponible para esta cuenta.',
    'Body must be a JSON object': 'La solicitud no es válida.',
    'Enter a valid email address': 'Escribe un correo electrónico válido.',
    'Enter an amount and a different recipient email': 'Escribe un monto y el correo de otra persona.',
    'Invalid or missing token': 'La clave de acceso no es válida o falta.',
    'Method not allowed': 'Método no permitido.',
    'Not enough credit for that transfer': 'No tienes suficiente crédito para esa transferencia.',
    'Not found': 'No encontrado.',
    'Provide the link token, or your email and code': 'Usa el enlace, o escribe tu correo y el código.',
    'Sign in required': 'Necesitas iniciar sesión.',
    'That billing interval is not offered for this plan': 'Ese periodo de facturación no está disponible para este plan.',
    'That code is invalid or has already been used.': 'Ese código no es válido o ya se usó.',
    'That option is not offered for this plan': 'Esa opción no está disponible para este plan.',
    'That sign-in link or code is invalid or has expired.': 'Ese enlace o código no es válido o ya venció.',
    'Too many sign-in emails. Try again in a few minutes.':
        'Demasiados correos para iniciar sesión. Intenta de nuevo en unos minutos.',
    'Unknown form': 'Formulario desconocido.',
    'Unknown plan or interval': 'Plan o periodo desconocido.',
    'Unknown plan or kind': 'Plan o tipo desconocido.',
    'amountCents must be a whole number': 'El monto debe ser un número entero.',
    'redirectUrl is not an allowed site URL': 'La dirección de regreso no es un sitio permitido.',
    'returnUrl is not an allowed site URL': 'La dirección de regreso no es un sitio permitido.',

    # Door check-in (staff; language follows the phone's browser)
    'Check-in': 'Registro',
    'Door check-in': 'Registro en la puerta',
    'Order is {0}. Do not admit.': 'La orden está {0}. No dejar pasar.',
    'Checked in. Enjoy the show.': 'Registrado. Disfruta el show.',
    'Already checked in at {0}.': 'Ya se registró a las {0}.',
    'Reserved, not paid: collect {0} for this seat, then check in.':
        'Reservado sin pagar: cobra {0} por este lugar y después registra.',
    'Check in': 'Registrar',
    # Unsubscribe page and the footer line on bulk email.
    'Email preferences': 'Preferencias de correo',
    'That link is not valid': 'Ese enlace no es válido',
    'Write to hello@iguanacomedy.com and we will take you off the list by hand.':
        'Escríbenos a hello@iguanacomedy.com y te sacamos de la lista a mano.',
    'You are on the list': 'Estás en la lista',
    'We email {0} when new shows go on sale.': 'Escribimos a {0} cuando salen shows nuevos a la venta.',
    'Unsubscribe': 'Cancelar suscripción',
    'You are unsubscribed': 'Cancelaste tu suscripción',
    'We will not email {0} about new shows again. Tickets you already bought are not affected.':
        'No volveremos a escribir a {0} sobre shows nuevos. Los boletos que ya compraste no se ven afectados.',
    'Changed your mind? Resubscribe': '¿Cambiaste de opinión? Vuelve a suscribirte',
    'You are receiving this because you signed up at iguanacomedy.com.':
        'Recibes esto porque te suscribiste en iguanacomedy.com.',
    'Unsubscribe: {0}': 'Cancelar suscripción: {0}',
    # Weekly what-is-on email (crm/whats_on.py)
    'This week at Iguana Comedy, Playa del Carmen:': 'Esta semana en Iguana Comedy, Playa del Carmen:',
    'This week at Iguana Comedy: {0}': 'Esta semana en Iguana Comedy: {0}',
    'This week at Iguana Comedy: open mic Tuesday and Wednesday':
        'Esta semana en Iguana Comedy: open mic martes y miércoles',
    'Sign-up list {0}, show {1}. Free entry.': 'Lista {0}, show {1}. Entrada gratis.',
    'Doors {0}, show {1}. Free entry.': 'Puertas {0}, show {1}. Entrada gratis.',
    'Hold your seat for {0}, a free drink included: {1}':
        'Aparta tu lugar por {0}, incluye una bebida gratis: {1}',
    # The share link somebody sends after booking, and the morning-after note.
    'I am going to see {0} at Iguana Comedy. Tickets here: {1}':
        'Voy a ver a {0} en Iguana Comedy. Boletos aquí: {1}',
    'Shows here sell out. Send this to whoever you want to bring and they can get their own ticket.':
        'Los shows aquí se llenan. Manda esto a quien quieras traer y puede sacar su propio boleto.',
    # The staff reservations board: how many we have for each night, and who they are.
    # The spend-against-bookings page.
    'The room, night by night': 'La sala, noche por noche',
    'Today, from visit to booking': 'Hoy, de la visita a la reservación',
    'visits': 'visitas',
    'started booking': 'empezaron a reservar',
    'booked': 'reservaron',
    'Over seven days: {0} visits, {1} started, {2} booked.':
        'En siete días: {0} visitas, {1} empezaron, {2} reservaron.',
    'Everything else': 'Lo demás',
    '{0} people on the mailing list, {1} joined this week.':
        '{0} personas en la lista de correo, {1} se sumaron esta semana.',
    '{0} table(s) open at the bar, {1} owed': '{0} mesa(s) abiertas en la barra, {1} por cobrar',
    'Stats': 'Números',
    'Spend from Meta, {0} ago': 'Gasto según Meta, hace {0}',
    'No spend figures yet': 'Todavía no hay cifras de gasto',
    'These spend figures are not fresh. The snapshot cron has not written in a while, so treat the cost per seat as the last known one.':
        'Estas cifras de gasto no están frescas. El cron no ha escrito en un rato, así que toma el costo por lugar como el último conocido.',
    'Today so far': 'Hoy hasta ahora',
    'Yesterday': 'Ayer',
    'Last 7 days': 'Últimos 7 días',
    '{0} spent': '{0} gastados',
    'The day is {0}% through. Spend runs from midnight while bookings arrive in the evening, so this reads high in the afternoon.':
        'Va {0}% del día. El gasto corre desde medianoche y las reservaciones llegan de noche, así que por la tarde se ve alto.',
    'Free reservations': 'Reservaciones gratis',
    'Paid tickets': 'Boletos pagados',
    'seat': 'lugar',
    'no seats yet': 'sin lugares todavía',
    'Ad spend': 'Gasto en anuncios',
    'Bookings': 'Reservaciones',
    'Per booking': 'Por reservación',
    'Taken': 'Cobrado',
    'Return': 'Retorno',
    'Ads as share': 'Anuncios como parte',
    'Bookings and seats are our own rows, counted now. Spend is Meta\'s, from the snapshot. Cost per seat is their spend over our seats, never over their purchase count: today they report {0} purchases against the {1} bookings we actually hold.':
        'Las reservaciones y los lugares son nuestros propios registros, contados ahora. El gasto es de Meta, del snapshot. El costo por lugar es su gasto entre nuestros lugares, nunca entre su conteo de compras: hoy reportan {0} compras contra las {1} reservaciones que realmente tenemos.',
    # The bar board's running tab: what this table owes for the night, not just what is waiting.
    'Mark paid': 'Marcar pagado',
    'Paid': 'Pagado',
    'Undo': 'Deshacer',
    'Not paid after all': 'No pagó después de todo',
    '1 round tonight': '1 ronda esta noche',
    '1 round · {0} drinks': '1 ronda · {0} bebidas',
    '{0} rounds tonight': '{0} rondas esta noche',
    '{0} taken': '{0} cobrados',
    '{0} still owed': '{0} por cobrar',
    'The bar, night by night': 'La barra, noche por noche',
    '{0} rounds · {1} drinks': '{0} rondas · {1} bebidas',
    'nothing yet': 'nada todavía',
    'Waiting now': 'Pendientes ahora',
    '{0} min': '{0} min',
    'See breakdown': 'Ver desglose',
    'Hide breakdown': 'Ocultar desglose',
    'Waiting': 'Pendiente',
    'Delivered at the table': 'Entregado en la mesa',
    'Paid for': 'Pagado',
    'Due': 'Por cobrar',
    '{0} rounds': '{0} rondas',
    'Nothing waiting': 'Nada pendiente',
    'Reservations': 'Reservaciones',
    '{0} seats booked across every night to come': '{0} lugares apartados en todas las noches por venir',
    'show {0}': 'show {0}',
    'tonight': 'esta noche',
    '1 booking': '1 reservación',
    '{0} bookings': '{0} reservaciones',
    '{0} left': 'quedan {0}',
    '{0} sold elsewhere': '{0} vendidos por otro lado',
    '{0} taken online': '{0} cobrados en línea',
    '{0} to collect at the door': '{0} por cobrar en la puerta',
    '{0} checked in': '{0} registrados en la puerta',
    'Who is coming': 'Quién viene',
    'Name': 'Nombre',
    'Seats': 'Lugares',
    'Booked': 'Reservó',
    'Nobody yet.': 'Nadie todavía.',
    'Nothing on the calendar yet.': 'Nada en el calendario todavía.',
    'Recent nights': 'Noches recientes',
    'nobody was scanned at the door': 'nadie fue registrado en la puerta',
    'How was last night?': '¿Qué tal estuvo anoche?',
    'You had a seat for {0} last night. We hope you made it, and that it was a good one.':
        'Tenías lugar para {0} anoche. Esperamos que hayas podido venir y que la hayas pasado bien.',
    'If you enjoyed it, tell somebody. The open mic is every week and free to reserve:':
        'Si te gustó, cuéntaselo a alguien. El open mic es cada semana y reservar es gratis:',
    'And if anything could have been better, just reply to this email. We read every one.':
        'Y si algo pudo haber estado mejor, solo responde a este correo. Los leemos todos.',
    'See you at the next one,': 'Nos vemos en la próxima,',
    'Show {0}.': 'Show {0}.',
    'Tickets from {0}: {1}': 'Boletos desde {0}: {1}',
    'Details: {0}': 'Más información: {0}',
    'Everything that is on: {0}': 'Toda la cartelera: {0}',
    'See you at the club,': 'Nos vemos en el club,',
    # Confirmed opt-in (crm/optin.py, templates/embed/newsletter_confirmed.html)
    'Confirm your email': 'Confirma tu correo',
    'Confirm you want our weekly email about what is on at Iguana Comedy:':
        'Confirma que quieres nuestro correo semanal con lo que hay en Iguana Comedy:',
    'If you did not ask for this, ignore this email and nothing else will be sent.':
        'Si no lo pediste, ignora este correo y no te mandaremos nada más.',
    'Every Monday morning we send {0} one email with what is on that week.':
        'Cada lunes por la mañana mandamos a {0} un correo con lo que hay esa semana.',
    'It may have expired. Sign up again on the site and we will send a new one.':
        'Quizá caducó. Vuelve a registrarte en el sitio y te mandamos otro.',
    'Back to the site': 'Volver al sitio',
    # Free open mic reservation + the drinks upsell
    'Reserve my free spot': 'Reserva mi lugar gratis',
    'Reserve {0} free spots': 'Reserva {0} lugares gratis',
    'Nothing to pay': 'No pagas nada',
    'Want to order your drinks in advance?': '¿Quieres pedir tus bebidas por adelantado?',
    'or pay by card': 'o paga con tarjeta',
    'plus drinks': 'y bebidas',
    # The bar menu ordered from a table (api/menu_views.py)
    'That table number does not exist.': 'Ese número de mesa no existe.',
    'Choose something first.': 'Elige algo primero.',
    'Those items are not available right now.': 'Esos productos no están disponibles ahora.',
    'Order sent to the bar. Someone will bring it to table {0}.':
        'Pedido enviado a la barra. Alguien lo lleva a la mesa {0}.',
    'Reserve a free seat: {0}': 'Reserva un lugar gratis: {0}',
    # The demand line above the reserve button (sales/demand.py)
    'in the last hour': 'en la última hora',
    'in the last few hours': 'en las últimas horas',
    'in the last day': 'en el último día',
    '{0} people reserved {1}': '{0} personas reservaron {1}',
    'Only {0} seats left of {1}': 'Solo quedan {0} lugares de {1}',
    '{0} of {1} seats taken': '{0} de {1} lugares apartados',
    # Invite a friend, after reserving (sales/sharing.py, templates/embed/order.html)
    # The bar, offered after the seat is held rather than inside the checkout (templates/embed/order.html)
    'Thirsty?': '¿Con sed?',
    'Have a look at what is behind the bar. On the night you can order from your table with the code on it, so '
    'you do not have to get up during a set.':
        'Echa un ojo a lo que hay en la barra. La noche del show puedes pedir desde tu mesa con el código que '
        'tiene, para no levantarte a media rutina.',
    'See the menu': 'Ver el menú',
    # The bar's board (api/tables_views.py, templates/embed/tables.html)
    'Tables': 'Mesas',
    'Table': 'Mesa',
    '{0} waiting': '{0} esperando',
    'Nothing waiting': 'Nada esperando',
    'Nothing ordered': 'Sin pedidos',
    'just now': 'ahora mismo',
    '{0} min ago': 'hace {0} min',
    'Delivered': 'Entregado',
    'This page refreshes itself. A table disappears once it is marked delivered.':
        'Esta página se actualiza sola. Una mesa desaparece al marcarla como entregada.',
    'Bringing someone?': '¿Vienes con alguien?',
    'These nights fill up. Send this to whoever you want to bring and they can reserve their own free seat.':
        'Estas noches se llenan. Manda esto a quien quieras traer y aparta su lugar gratis.',
    'Invite on WhatsApp': 'Invitar por WhatsApp',
    'Copy the link': 'Copiar el enlace',
    'Link copied': 'Enlace copiado',
    'Bringing someone? Send them this and they can reserve their own free seat:':
        '¿Vienes con alguien? Mándale esto y aparta su lugar gratis:',
    'I am going to the open mic at Iguana Comedy. Entry is free, reserve a seat here: {0}':
        'Voy al open mic de Iguana Comedy. La entrada es gratis, aparta tu lugar aquí: {0}',
}


def normalize(lang):
    """Anything Spanish ('es', 'es-MX', 'ES') becomes 'es'; everything else is English."""
    return 'es' if str(lang or '').strip().lower().startswith('es') else 'en'


def tr(lang, text, *params):
    template = ES.get(text, text) if normalize(lang) == 'es' else text
    return template.format(*params) if params else template


def locale_from_request(request):
    """The language a browser call belongs to: the explicit parameter, then our own header, then the page that
    made the call. Some SDK methods take no locale argument, and the referring /es/ or /en/ path is the only
    signal they carry."""
    explicit = request.GET.get('locale') or request.headers.get('X-Iguana-Locale', '')
    if explicit:
        return normalize(explicit)
    referer = request.headers.get('Referer', '')
    try:
        first = urlparse(referer).path.strip('/').split('/')[0]
    except ValueError:
        first = ''
    return normalize(first)


def lang_from_request(request):
    """The browser's preferred language, for pages with no order or page locale to follow (door check-in)."""
    return normalize(request.headers.get('Accept-Language', ''))
