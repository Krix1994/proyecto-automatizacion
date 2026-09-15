"""
Pruebas de regresión: Facturación - Dent-OS
Casos cubiertos:
  #1  Factura con 2 formas de pago
  #2  Factura aplicando descuento
  #3  Factura por empresa (a nombre de un tercero)
"""

import pytest
from playwright.sync_api import Page, expect


def test_factura_dos_formas_pago(pagina_con_paciente: Page):
    """
    #1 - Desde el plan de tto se cancela factura usando doble forma de pago.
    """
    page = pagina_con_paciente
    # TODO: grabar pasos reales con Codegen:
    #   playwright codegen https://release.dentos.co/auth/login
    pytest.skip("Pendiente: grabar pasos reales con Codegen")


def test_factura_aplicar_descuento(pagina_con_paciente: Page):
    """
    #2 - Se cancela factura aplicando descuento al procedimiento.
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")


def test_factura_por_empresa(pagina_con_paciente: Page):
    """
    #3 - Se cancela factura generándola a nombre de un tercero (empresa).
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")
