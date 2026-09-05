"""
Testes da camada geografica de mercado (Minas Gerais).

Dois grupos:

  1. Puros — normalizacao e pareamento de nomes de cidade. Rodam sem banco.
     Sao os que impedem a regressao mais perigosa desta camada: parear
     'Anapolis' (GO) com 'Canapolis' (MG) e colocar mercado no municipio errado.

  2. De integracao — coerencia da camada carregada no banco. Pulados quando
     a base de mercado ainda nao foi construida.
"""
from __future__ import annotations

import polars as pl
import pytest

from src.db.engine import count_rows, read_sql, table_exists
from src.staging.geografia import _parear, normalizar_cidade

# =====================================================================
# 1. Normalizacao e pareamento (sem banco)
# =====================================================================

SUFIXOS = [", Minas Gerais", " - MG", ", MG", " (MG)", " MG"]


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Campo Azul, Minas Gerais", "CAMPO AZUL"),
        ("5357-UBERLANDIA", "UBERLANDIA"),
        ("São Gonçalo do Pará", "SAO GONCALO DO PARA"),
        ("São João del-Rei", "SAO JOAO DEL REI"),
        ("  Ouro   Preto  ", "OURO PRETO"),
        ("Uberaba (MG)", "UBERABA"),
        (None, ""),
    ],
)
def test_normalizacao_de_cidade(entrada, esperado):
    assert normalizar_cidade(entrada, SUFIXOS) == esperado


CATALOGO = {
    "UBERLANDIA": 3170206,
    "SAO DOMINGOS DO PRATA": 3161908,
    "SAO SEBASTIAO DO PARAISO": 3162500,
    "CANAPOLIS": 3112307,
    "GOIANA": 3127354,          # Goiana-MG existe; Goiania e de GO
    "MIRAI": 3142007,
    "IRAI DE MINAS": 3131901,
    "CAMPOS ALTOS": 3112505,
    "CRUZEIRO DA FORTALEZA": 3120904,
}


def _metodo(nome: str) -> tuple[str, int | None]:
    resultado = _parear([nome], CATALOGO, SUFIXOS)[0]
    return resultado["metodo"], resultado["cod_ibge"]


def test_pareamento_exato():
    assert _metodo("UBERLANDIA") == ("EXATO", 3170206)


def test_pareamento_ignora_conectivos():
    """'SAO DOMINGOS PRATA' e 'Sao Domingos do Prata' sao o mesmo municipio."""
    metodo, cod = _metodo("SAO DOMINGOS PRATA")
    assert metodo == "SEM_CONECTIVOS"
    assert cod == 3161908


def test_pareamento_expande_abreviacao():
    """O cadastro do ERP abrevia 'Sao' como 'S.'."""
    metodo, cod = _metodo("S. SEBASTIAO PARAISO")
    assert metodo == "SEM_CONECTIVOS"
    assert cod == 3162500


def test_pareamento_aceita_plural_proximo():
    metodo, cod = _metodo("CAMPOS ALTO")
    assert metodo == "APROXIMADO"
    assert cod == 3112505


@pytest.mark.parametrize("cidade", ["ANAPOLIS", "GOIANIA", "APARECIDA DE GOIANIA"])
def test_cidade_de_outro_estado_nao_e_forcada_para_mg(cidade):
    """
    O arquivo de territorio contem cidades de GO, SP, MT e DF. Nenhuma delas
    pode acabar pintada num municipio de Minas so por semelhanca de grafia -
    foi exatamente o erro que 'ANAPOLIS' -> 'Canapolis' produzia.
    """
    metodo, cod = _metodo(cidade)
    assert cod is None
    assert metodo in {"NAO_ENCONTRADO", "AMBIGUO"}


def test_grafia_ambigua_nao_escolhe_sozinha():
    """'IRAI' poderia ser 'Irai de Minas' ou 'Mirai': na duvida, nao decide."""
    metodo, cod = _metodo("IRAI")
    assert cod is None
    assert metodo in {"NAO_ENCONTRADO", "AMBIGUO"}


# =====================================================================
# 2. Integracao com o banco
# =====================================================================

pytestmark_integracao = pytest.mark.skipif(
    not table_exists("analytics", "dim_municipio_mg")
    or count_rows("analytics", "dim_municipio_mg") == 0,
    reason="Base de mercado não construída. Rode: py scripts/build_mercado_mg.py",
)


@pytestmark_integracao
def test_universo_municipal_completo():
    """Minas Gerais tem 853 municipios: o denominador precisa estar inteiro."""
    assert count_rows("analytics", "dim_municipio_mg") == 853


@pytestmark_integracao
def test_toda_cidade_de_cliente_mg_tem_municipio():
    """
    Se uma cidade de cliente ficasse sem codigo IBGE, a venda dela sumiria do
    mapa sem aviso — e o total do estado passaria a divergir do da pagina de
    Vendas. A lacuna precisa ser zero ou explicita.
    """
    orfas = read_sql(
        """
        SELECT COUNT(*) AS n
        FROM analytics.map_cidade_ibge
        WHERE origem = 'CLIENTE' AND cod_ibge IS NULL
        """
    ).row(0)[0]
    assert orfas == 0


@pytestmark_integracao
def test_venda_do_mapa_bate_com_o_fato():
    """
    A tonelagem que chega ao mapa municipal tem de ser a mesma do fato de
    venda em MG. Divergencia aqui significa cidade perdida no pareamento.
    """
    do_mapa = read_sql(
        "SELECT COALESCE(SUM(ton_liquida), 0) FROM analytics.mv_vendas_municipio_mg"
    ).row(0)[0]
    do_fato = read_sql(
        "SELECT COALESCE(SUM(tonliq), 0) FROM analytics.v_venda_item WHERE uf_cliente = 'MG'"
    ).row(0)[0]
    assert float(do_fato) != 0
    diferenca_pct = abs(float(do_mapa) - float(do_fato)) / abs(float(do_fato)) * 100
    assert diferenca_pct < 0.01, f"mapa {do_mapa} x fato {do_fato} ({diferenca_pct:.4f}%)"


@pytestmark_integracao
def test_potencial_nunca_e_negativo():
    negativos = read_sql(
        """
        SELECT COUNT(*) FROM analytics.fact_potencial_municipio
        WHERE potencial_t_mes < 0 OR potencial_capturavel_t_mes < 0
        """
    ).row(0)[0]
    assert negativos == 0


@pytestmark_integracao
def test_capturavel_nunca_excede_o_enderecavel():
    """A probabilidade de captura e uma fracao: nao pode inflar o potencial."""
    invalidos = read_sql(
        """
        SELECT COUNT(*) FROM analytics.fact_potencial_municipio
        WHERE potencial_capturavel_t_mes > potencial_t_mes + 0.0001
        """
    ).row(0)[0]
    assert invalidos == 0


@pytestmark_integracao
def test_repositorio_reproduz_a_materialized_view():
    """
    A consulta parametrizada de src/repositories/geo.py e a MV consolidada
    precisam contar a mesma historia na janela padrao. Duas fontes que
    divergem seriam pior que uma so.
    """
    from src.repositories import geo

    do_repo = geo.municipios(janela_meses=12)
    da_mv = read_sql(
        "SELECT cod_ibge, ton_farinha_12m, teto_t_mes FROM ("
        "  SELECT cod_ibge, ton_farinha_12m, potencial_capturavel_t_mes AS teto_t_mes"
        "  FROM analytics.mv_mercado_municipio_mg) x"
    )
    assert do_repo.height == da_mv.height == 853

    juntos = do_repo.select("cod_ibge", "ton_farinha", "teto_t_mes").join(
        da_mv, on="cod_ibge", suffix="_mv"
    )
    dif_venda = (
        juntos.select(
            (pl.col("ton_farinha").cast(pl.Float64)
             - pl.col("ton_farinha_12m").cast(pl.Float64)).abs().max()
        ).item()
    )
    dif_teto = (
        juntos.select(
            (pl.col("teto_t_mes").cast(pl.Float64)
             - pl.col("teto_t_mes_mv").cast(pl.Float64)).abs().max()
        ).item()
    )
    assert float(dif_venda or 0) < 0.01
    assert float(dif_teto or 0) < 0.01


@pytestmark_integracao
def test_classificacao_cobre_todos_os_municipios():
    from src.repositories import geo

    df = geo.classificar(geo.municipios())
    assert df.height == 853
    assert df["quadrante"].null_count() == 0
    # Municipio sem venda nenhuma jamais pode ser classificado como venda alta.
    sem_venda_alta = df.filter(
        (pl.col("venda_t_mes") <= 0) & pl.col("quadrante").is_in(["ALTO_ALTA", "BAIXO_ALTA"])
    )
    assert sem_venda_alta.height == 0


@pytestmark_integracao
def test_resumo_do_estado_e_coerente():
    from src.repositories import geo

    df = geo.municipios()
    r = geo.resumo_estado(df)
    assert r["municipios"] == 853
    assert 0 < r["com_venda"] < 853
    assert r["com_venda"] + r["sem_venda"] == 853
    # O teto realista e uma fracao do enderecavel, nunca o contrario.
    assert r["teto_t_mes"] <= r["enderecavel_t_mes"]
    assert r["espaco_t_mes"] >= 0


@pytestmark_integracao
def test_territorio_so_contem_municipios_de_mg():
    fora = read_sql(
        """
        SELECT COUNT(*) FROM analytics.dim_territorio_rca t
        LEFT JOIN analytics.dim_municipio_mg m ON m.cod_ibge = t.cod_ibge
        WHERE m.cod_ibge IS NULL
        """
    ).row(0)[0]
    assert fora == 0
