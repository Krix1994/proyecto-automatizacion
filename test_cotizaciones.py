"""
Pruebas de regresión: Cotizaciones - Dent-OS
Casos cubiertos:
  #11  Crear cotización
  #12  Imprimir cotización
  #13  Convertir cotización a Plan de Tratamiento (PTT)
  #14  Modificar cotización
  #15  Eliminar cotización
"""

import pytest
from playwright.sync_api import Page, expect


def test_crear_cotizacion(pagina_con_paciente: Page):
    """
    #11 - En el plan de tto del paciente, sección de cotización,
    crear y guardar con datos.
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")


def test_imprimir_cotizacion(pagina_con_paciente: Page):
    """
    #12 - Botón de imprimir sobre la cotización creada.
    Nota: probablemente depende de que ya exista una cotización
    (ver test_crear_cotizacion).
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")


def test_convertir_cotizacion_a_ptt(pagina_con_paciente: Page):
    """
    #13 - En el listado de cotizaciones, convertir la cotización
    a Plan de Tratamiento.
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")


def test_modificar_cotizacion(pagina_con_paciente: Page):
    """
    #14 - En el listado de cotizaciones, modificar la cotización.
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")


def test_eliminar_cotizacion(pagina_con_paciente: Page):
    """
    #15 - En el listado de cotizaciones, eliminar la cotización.
    """
    page = pagina_con_paciente
    pytest.skip("Pendiente: grabar pasos reales con Codegen")
