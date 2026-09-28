import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from api.floor import floor_group
from catalog.models import InventoryItem, MenuCategory, MenuItem, MenuItemIngredient

from . import services
from .models import (Check, CheckLine, Comanda, Modifier, ModifierGroup, Payment, Printer, PrintJob, Shift, Staff,
                     StockCount, Table, Zone)
from .services import PosError


def staff(name, role, pin):
    s = Staff(name=name, role=role)
    s.set_pin(pin)
    s.save()
    return s


@override_settings(STRIPE_SECRET_KEY='', STRIPE_PUBLISHABLE_KEY='', NOTIFY_EMAILS=[], DEBUG=True,
                   SITE_URLS=['http://site.test'])
class PosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.zone = Zone.objects.create(name='Salón')
        cls.t1 = Table.objects.create(zone=cls.zone, number=1)
        cls.t2 = Table.objects.create(zone=cls.zone, number=2)
        cls.cat = MenuCategory.objects.create(name='Cervezas', name_es='Cervezas')
        cls.beer = MenuItem.objects.create(category=cls.cat, name='Corona', name_es='Corona', price_cents=6000)
        cls.shot = MenuItem.objects.create(category=cls.cat, name='Tequila', name_es='Tequila', price_cents=9000)
        cls.stock = InventoryItem.objects.create(name='Corona', unit='pieza', quantity=Decimal('24'))
        MenuItemIngredient.objects.create(menu_item=cls.beer, inventory_item=cls.stock, quantity=1)
        cls.waiter = staff('Ana', Staff.MESERO, '1111')
        cls.cashier = staff('Beto', Staff.CAJERO, '2222')
        cls.manager = staff('Caro', Staff.GERENTE, '3333')

    def floor_client(self, pin=None):
        user = get_user_model().objects.create_user(f'mesero{Staff.objects.count()}{timezone.now().timestamp()}',
                                                    password='x')
        user.groups.add(floor_group())
        self.client.force_login(user)
        if pin:
            self.client.post('/pos/entrar/', {'pin': pin})
        return self.client

    def post(self, url, body=None):
        return self.client.post(url, json.dumps(body or {}), content_type='application/json')


class ServicesTests(PosTestCase):
    def test_a_table_has_one_open_check_however_many_waiters_tap_it(self):
        a = services.open_check(table=self.t1, waiter=self.waiter)
        b = services.open_check(table=self.t1, waiter=self.cashier)
        self.assertEqual(a.pk, b.pk)

    def test_sending_takes_stock_once_and_queues_a_comanda(self):
        cuenta = services.open_check(table=self.t1, waiter=self.waiter)
        services.add_line(cuenta, self.beer, quantity=3, by=self.waiter)
        comanda = services.send(cuenta, self.waiter)
        self.assertEqual(comanda.number, 1)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, Decimal('21'))
        self.assertIsNone(services.send(cuenta, self.waiter), 'nothing new, nothing sent')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, Decimal('21'))
        job = PrintJob.objects.get(role=Printer.COMANDA)
        self.assertIn('Corona', '\n'.join(job.lines))

    def test_an_unsent_line_just_goes_but_a_sent_one_needs_a_manager(self):
        cuenta = services.open_check(table=self.t1)
        draft = services.add_line(cuenta, self.beer)
        services.void_line(draft, reason=CheckLine.NOT_MADE)
        self.assertFalse(CheckLine.objects.filter(pk=draft.pk).exists())
        sent = services.add_line(cuenta, self.beer)
        services.send(cuenta, self.waiter)
        with self.assertRaises(PosError):
            services.void_line(sent, reason=CheckLine.NOT_MADE, manager=self.waiter)
        services.void_line(sent, reason=CheckLine.NOT_MADE, manager=self.manager)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, Decimal('24'), 'not made: back on the shelf')

    def test_a_drink_made_and_binned_stays_out_of_stock(self):
        cuenta = services.open_check(table=self.t1)
        line = services.add_line(cuenta, self.beer)
        services.send(cuenta)
        services.void_line(line, reason=CheckLine.WASTED, manager=self.manager)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, Decimal('23'))
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.total_cents, 0)

    def test_paying_needs_an_open_shift(self):
        cuenta = services.open_check(table=self.t1)
        services.add_line(cuenta, self.beer)
        with self.assertRaises(PosError):
            services.pay(cuenta, method=Payment.CASH, amount_cents=6000, by=self.cashier)

    def test_cash_with_change_closes_the_check_and_sends_what_was_left(self):
        services.open_shift(self.cashier, 50000)
        cuenta = services.open_check(table=self.t1)
        services.add_line(cuenta, self.beer, quantity=2)
        services.pay(cuenta, method=Payment.CASH, amount_cents=12000, tip_cents=1000, received_cents=20000,
                     by=self.cashier)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.status, Check.PAID)
        self.assertEqual(cuenta.payments.get().change_cents, 7000)
        self.assertFalse(cuenta.unsent, 'paying sends anything still unsent')
        self.assertTrue(PrintJob.objects.filter(title__startswith='Ticket').exists())

    def test_split_payments_close_on_the_last_one(self):
        services.open_shift(self.cashier, 0)
        cuenta = services.open_check(table=self.t1)
        services.add_line(cuenta, self.shot, quantity=2)
        services.pay(cuenta, method=Payment.CARD, amount_cents=9000, reference='1234', by=self.cashier)
        cuenta.refresh_from_db()
        self.assertEqual((cuenta.status, cuenta.due_cents), (Check.OPEN, 9000))
        with self.assertRaises(PosError):
            services.pay(cuenta, method=Payment.CASH, amount_cents=10000, by=self.cashier)
        services.pay(cuenta, method=Payment.TRANSFER, amount_cents=9000, by=self.cashier)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.status, Check.PAID)

    def test_courtesy_and_discount_need_a_manager(self):
        services.open_shift(self.cashier, 0)
        cuenta = services.open_check(table=self.t1)
        services.add_line(cuenta, self.shot)
        with self.assertRaises(PosError):
            services.set_discount(cuenta, percent=50, manager=self.cashier)
        services.set_discount(cuenta, percent=50, reason='cumpleaños', manager=self.manager)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.total_cents, 4500)
        with self.assertRaises(PosError):
            services.pay(cuenta, method=Payment.COURTESY, amount_cents=4500, by=self.cashier)
        services.pay(cuenta, method=Payment.COURTESY, amount_cents=4500, by=self.cashier, manager=self.manager)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.status, Check.PAID)

    def test_moving_onto_an_occupied_table_joins_the_checks(self):
        a = services.open_check(table=self.t1)
        services.add_line(a, self.beer)
        b = services.open_check(table=self.t2)
        services.add_line(b, self.shot)
        joined = services.move(a, self.t2)
        self.assertEqual(joined.pk, b.pk)
        self.assertEqual(joined.total_cents, 15000)
        a.refresh_from_db()
        self.assertEqual(a.status, Check.CANCELLED)

    def test_split_moves_the_chosen_lines_to_a_new_check(self):
        cuenta = services.open_check(table=self.t1)
        keep = services.add_line(cuenta, self.beer)
        move = services.add_line(cuenta, self.shot)
        new = services.split(cuenta, [move.pk])
        self.assertEqual(new.table, self.t1)
        self.assertEqual(new.total_cents, 9000)
        self.assertEqual(Check.objects.get(pk=cuenta.pk).total_cents, 6000)
        with self.assertRaises(PosError):
            services.split(cuenta, [keep.pk])

    def test_cancelling_a_check_returns_what_was_sent(self):
        cuenta = services.open_check(table=self.t1)
        services.add_line(cuenta, self.beer, quantity=2)
        services.send(cuenta)
        services.cancel_check(cuenta, reason='se fueron', manager=self.manager)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, Decimal('24'))

    def test_the_corte_expects_fondo_plus_cash_plus_cash_tips_minus_retiros(self):
        shift = services.open_shift(self.cashier, 50000)
        cuenta = services.open_check(table=self.t1)
        services.add_line(cuenta, self.shot)
        services.pay(cuenta, method=Payment.CASH, amount_cents=9000, tip_cents=1000, by=self.cashier)
        services.cash_move(shift, 'OUT', 20000, 'caja fuerte', self.manager)
        services.close_shift(shift, self.manager, counted_cash_cents=40000)
        s = services.shift_summary(Shift.objects.get(pk=shift.pk))
        self.assertEqual(s['expected_cash'], 50000 + 9000 + 1000 - 20000)
        self.assertEqual(s['cash_difference'], 0)
        self.assertEqual(s['sales'], 9000)

    def test_a_qr_order_lands_unsent_on_the_tables_check(self):
        cuenta, lines = services.customer_order(1, {self.beer.id: 2}, name='Luis', note='sin limón')
        self.assertEqual(cuenta.table, self.t1)
        self.assertTrue(all(l.from_customer and not l.sent_at for l in lines))
        again, _ = services.customer_order(1, {self.shot.id: 1})
        self.assertEqual(again.pk, cuenta.pk)

    def test_a_qr_order_for_a_table_not_on_the_map_adds_it(self):
        cuenta, _ = services.customer_order(15, {self.beer.id: 1})
        self.assertEqual(cuenta.table.number, 15)

    def test_modifiers_add_their_price_and_only_their_own(self):
        g = ModifierGroup.objects.create(name='Preparación')
        g.items.add(self.beer)
        mich = Modifier.objects.create(group=g, name='Michelada', price_cents=2000)
        other = ModifierGroup.objects.create(name='Otro')
        stray = Modifier.objects.create(group=other, name='Ajeno', price_cents=99900)
        cuenta = services.open_check(table=self.t1)
        line = services.add_line(cuenta, self.beer, modifier_ids=[mich.id, stray.id])
        self.assertEqual(line.each_cents, 8000)

    def test_a_purchase_adds_stock_and_sets_the_cost(self):
        services.record_purchase(supplier=None, lines=[(self.stock, Decimal('24'), 36000)], by=self.manager)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, Decimal('48'))
        self.assertEqual(self.stock.pos_cost.unit_cost_cents, 1500)

    def test_a_physical_count_replaces_the_sheet(self):
        count = services.start_count(self.manager)
        line = count.lines.get(item=self.stock)
        line.counted = Decimal('20')
        line.save()
        services.apply_count(count, self.manager)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, Decimal('20'))
        self.assertEqual(StockCount.objects.get(pk=count.pk).status, StockCount.APPLIED)


class ScreensTests(PosTestCase):
    def test_the_pin_pad_is_the_front_door(self):
        self.floor_client()
        self.assertRedirects(self.client.get('/pos/'), '/pos/entrar/?next=/pos/', fetch_redirect_response=False)
        res = self.client.post('/pos/entrar/', {'pin': '9999'})
        self.assertContains(res, 'PIN incorrecto')
        self.client.post('/pos/entrar/', {'pin': '1111'})
        self.assertContains(self.client.get('/pos/'), 'Ana')

    def test_a_tablet_that_is_not_signed_in_goes_to_the_floor_login(self):
        res = self.client.get('/pos/entrar/')
        self.assertTrue(res['Location'].startswith('/mesas/entrar/'))

    def test_every_screen_opens_for_a_manager(self):
        self.floor_client('3333')
        services.open_shift(self.manager, 0)
        cuenta = services.open_check(table=self.t1, waiter=self.manager)
        for url in ('/pos/', '/pos/barra/', '/pos/caja/', '/pos/inventario/', '/pos/inventario/compras/',
                    '/pos/inventario/conteo/', '/pos/inventario/insumo/', '/pos/productos/', '/pos/productos/nuevo/',
                    f'/pos/productos/{self.beer.pk}/', '/pos/productos/modificadores/', '/pos/reportes/',
                    '/pos/personal/', '/pos/mesas/', '/pos/impresoras/', '/pos/imprimir/', f'/pos/cuenta/{cuenta.pk}/',
                    f'/pos/pagar/{cuenta.pay_token}/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_a_waiter_cannot_open_the_managers_screens(self):
        self.floor_client('1111')
        for url in ('/pos/productos/', '/pos/reportes/', '/pos/personal/', '/pos/caja/'):
            self.assertEqual(self.client.get(url)['Location'], '/pos/?denied=1', url)

    def test_the_order_screen_round_trip(self):
        self.floor_client('1111')
        res = self.client.get(f'/pos/mesa/{self.t1.pk}/')
        cuenta = Check.objects.get(table=self.t1)
        self.assertRedirects(res, f'/pos/cuenta/{cuenta.pk}/', fetch_redirect_response=False)
        data = self.post(f'/pos/api/cuenta/{cuenta.pk}/agregar/', {'item': self.beer.pk}).json()
        self.assertEqual(data['cuenta']['total'], 6000)
        data = self.post(f'/pos/api/cuenta/{cuenta.pk}/enviar/').json()
        self.assertEqual(data['cuenta']['unsent'], 0)
        self.assertTrue(data['print'][0]['browser'], 'no printer yet: the tablet prints it')
        line = data['cuenta']['lines'][0]['id']
        refused = self.post(f'/pos/api/linea/{line}/cancelar/', {'reason': 'NOT_MADE'})
        self.assertEqual(refused.status_code, 400)
        ok = self.post(f'/pos/api/linea/{line}/cancelar/', {'reason': 'NOT_MADE', 'managerPin': '3333'})
        self.assertEqual(ok.json()['cuenta']['total'], 0)

    def test_a_waiter_charges_only_with_a_cashiers_pin(self):
        services.open_shift(self.cashier, 0)
        self.floor_client('1111')
        cuenta = services.open_check(table=self.t1, waiter=self.waiter)
        services.add_line(cuenta, self.beer)
        self.assertEqual(self.post(f'/pos/api/cuenta/{cuenta.pk}/pagar/', {'method': 'CASH', 'amount': '60'}).status_code, 400)
        res = self.post(f'/pos/api/cuenta/{cuenta.pk}/pagar/', {'method': 'CASH', 'amount': '60', 'managerPin': '3333'})
        self.assertEqual(res.json()['cuenta']['status'], 'PAID')

    def test_the_map_colours_a_waiting_qr_order(self):
        services.customer_order(2, {self.beer.id: 1})
        self.floor_client('1111')
        state = {t['number']: t['state'] for t in self.client.get('/pos/api/mapa/').json()['tables']}
        self.assertEqual((state[1], state[2]), ('free', 'order'))

    def test_the_old_board_now_points_here(self):
        self.floor_client('1111')
        self.assertEqual(self.client.get('/mesas/')['Location'], '/pos/')


class PhoneAndPrinterTests(PosTestCase):
    def test_a_phone_payment_closes_the_check(self):
        cuenta = services.open_check(table=self.t1)
        services.add_line(cuenta, self.beer)
        page = self.client.get(f'/pos/pagar/{cuenta.pay_token}/')
        self.assertContains(page, 'Corona')
        intent = self.client.post(f'/pos/pagar/{cuenta.pay_token}/intent/', {'tip': '10'}).json()
        done = self.client.post(f'/pos/pagar/{cuenta.pay_token}/confirmar/', {'paymentId': intent['paymentId']})
        self.assertEqual(done.status_code, 200)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.status, Check.PAID)
        self.assertEqual(cuenta.payments.get().tip_cents, 600)
        self.assertTrue(Comanda.objects.filter(cuenta=cuenta).exists(), 'paid by phone still reaches the bar')

    def test_an_epson_printer_fetches_its_jobs_and_reports_back(self):
        printer = Printer.objects.create(name='Barra', role=Printer.COMANDA, protocol=Printer.EPSON)
        cuenta = services.open_check(table=self.t1)
        services.add_line(cuenta, self.beer)
        services.send(cuenta)
        job = PrintJob.objects.get(printer=printer)
        res = self.client.post(f'/pos/print/{printer.token}/', {'ConnectionType': 'GetRequest'})
        self.assertIn(f'<printjobid>{job.id}</printjobid>', res.content.decode())
        self.assertIn('Corona', res.content.decode())
        self.client.post(f'/pos/print/{printer.token}/', {
            'ConnectionType': 'SetResponse',
            'ResponseFile': f'<PrintResponseInfo><ePOSPrint><Parameter><printjobid>{job.id}</printjobid></Parameter>'
                            f'<PrintResponse><response success="true" code=""/></PrintResponse></ePOSPrint></PrintResponseInfo>'})
        self.assertEqual(PrintJob.objects.get(pk=job.pk).status, PrintJob.DONE)

    def test_a_star_printer_polls_gets_and_deletes(self):
        printer = Printer.objects.create(name='Caja', role=Printer.TICKET, protocol=Printer.STAR)
        job = PrintJob.objects.create(role=Printer.TICKET, printer=printer, title='x', lines=['HOLA'])
        poll = self.client.post(f'/pos/print/{printer.token}/', '{}', content_type='application/json').json()
        self.assertEqual((poll['jobReady'], poll['jobToken']), (True, job.id))
        self.assertIn('HOLA', self.client.get(f'/pos/print/{printer.token}/?token={job.id}').content.decode())
        self.client.delete(f'/pos/print/{printer.token}/?token={job.id}&code=200%20OK')
        self.assertEqual(PrintJob.objects.get(pk=job.pk).status, PrintJob.DONE)
