# -*- coding: utf-8 -*-
"""
Covid-19 em São Paulo

Gera gráficos para acompanhamento da pandemia de Covid-19
na cidade e no estado de São Paulo.

@author: https://github.com/DaviSRodrigues
"""

from datetime import datetime, timedelta
from io import StringIO
import locale
from math import isnan, nan
from tableauscraper import TableauScraper
import traceback
import sys
import unicodedata

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import requests


def main():
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

    print(f'Carregando dados... {datetime.now():%H:%M:%S}')
    hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total = carrega_dados_cidade()
    dados_munic, dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, doses_aplicadas, doses_recebidas, dados_imunizantes, atualizacao_imunizantes = carrega_dados_estado()

    print(f'\nLimpando e enriquecendo dos dados... {datetime.now():%H:%M:%S}')
    dados_cidade, dados_munic, hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total, dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, dados_imunizantes = pre_processamento(hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total, dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, doses_aplicadas, doses_recebidas, dados_munic, dados_imunizantes, atualizacao_imunizantes)
    evolucao_cidade, evolucao_estado = gera_dados_evolucao_pandemia(dados_munic, dados_estado, isolamento, dados_vacinacao, internacoes)
    evolucao_cidade, evolucao_estado = gera_dados_semana(evolucao_cidade, evolucao_estado, leitos_estaduais, isolamento, internacoes)

    print(f'\nGerando gráficos e tabelas... {datetime.now():%H:%M:%S}')
    gera_graficos(dados_munic, dados_cidade, hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total, dados_estado, isolamento, leitos_estaduais, evolucao_cidade, evolucao_estado, internacoes, doencas, dados_raciais, dados_vacinacao, dados_imunizantes)

    print(f'\nAtualizando serviceWorker.js... {datetime.now():%H:%M:%S}')
    atualiza_service_worker(dados_estado)

    print('\nFim')


def carrega_dados_cidade():
    hospitais_campanha = pd.read_csv('dados/hospitais_campanha_sp.csv', sep=',')
    leitos_municipais = pd.read_csv('dados/leitos_municipais.csv', sep=',')
    leitos_municipais_privados = pd.read_csv('dados/leitos_municipais_privados.csv', sep=',')
    leitos_municipais_total = pd.read_csv('dados/leitos_municipais_total.csv', sep=',')

    return hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total


def carrega_dados_estado():
    hoje = data_processamento
    ano = hoje.strftime('%Y')
    mes = hoje.strftime('%m')
    data = hoje.strftime('%Y%m%d')

    try:
        print('\tAtualizando dados dos municípios...')
        URL = 'https://raw.githubusercontent.com/seade-R/dados-covid-sp/master/data/dados_covid_sp.csv'
        dados_munic = pd.read_csv(URL, sep=';', decimal=',')
        opcoes_zip = dict(method='zip', archive_name='dados_munic.csv')
        dados_munic.to_csv('dados/dados_munic.zip', sep=';', decimal=',', index=False, compression=opcoes_zip)
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        print('\tErro ao buscar dados_covid_sp.csv do GitHub: lendo arquivo local.\n')
        dados_munic = pd.read_csv('dados/dados_munic.zip', sep=';', decimal=',')

    try:
        print('\tAtualizando dados estaduais...')
        URL = 'https://raw.githubusercontent.com/seade-R/dados-covid-sp/master/data/sp.csv'
        dados_estado = pd.read_csv(URL, sep=';')
        dados_estado.to_csv('dados/dados_estado_sp.csv', sep=';')
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        print('\tErro ao buscar dados_estado_sp.csv do GitHub: lendo arquivo local.\n')
        dados_estado = pd.read_csv('dados/dados_estado_sp.csv', sep=';', decimal=',', encoding='latin-1', index_col=0)

    try:
        print('\tCarregando dados de isolamento social...')
        isolamento = pd.read_csv('dados/isolamento_social.csv', sep=',')
    except Exception as e:
        print(f'\tErro ao buscar isolamento_social.csv\n\t{e}')

    try:
        print('\tAtualizando dados de internações...')
        URL = ('https://raw.githubusercontent.com/seade-R/dados-covid-sp/master/data/plano_sp_leitos_internacoes.csv')
        internacoes = pd.read_csv(URL, sep=';', decimal=',', thousands='.')
        internacoes.to_csv('dados/internacoes.csv', sep=';', decimal=',')
    except Exception as e:
        try:
            print(f'\tErro ao buscar internacoes.csv do GitHub: lendo arquivo da Seade.\n\t{e}')
            URL = (f'http://www.seade.gov.br/wp-content/uploads/{ano}/{mes}/Leitos-e-Internacoes.csv')
            internacoes = pd.read_csv(URL, sep=';', encoding='latin-1', decimal=',', thousands='.', engine='python',
                                      skipfooter=2)
        except Exception as e:
            print(f'\tErro ao buscar internacoes.csv da Seade: lendo arquivo local.\n\t{e}')
            internacoes = pd.read_csv('dados/internacoes.csv', sep=';', decimal=',', thousands='.', index_col=0)

    try:
        print('\tAtualizando dados de doenças preexistentes...')
        URL = ('https://raw.githubusercontent.com/seade-R/dados-covid-sp/master/data/casos_obitos_doencas_preexistentes.csv.zip')
        doencas = pd.read_csv(URL, sep=';')
        if len(doencas.asma.unique()) == 3:
            opcoes_zip = dict(method='zip', archive_name='doencas_preexistentes.csv')
            doencas.to_csv('dados/doencas_preexistentes.zip', sep=';', compression=opcoes_zip)
        else:
            global processa_doencas
            processa_doencas = False
            raise Exception('O arquivo de doeças preexistentes não possui registros SIM/NÃO/IGNORADO para todas as doenças.')
    except Exception as e:
        try:
            print(f'\tErro ao buscar doencas_preexistentes.csv do GitHub: lendo arquivo local.\n\t{e}')
            doencas = pd.read_csv('dados/doencas_preexistentes.zip', sep=';', index_col=0)
        except Exception as e:
            print(f'\tErro ao buscar doencas_preexistentes.csv localmente: lendo arquivo da Seade.\n\t{e}')
            URL = f'http://www.seade.gov.br/wp-content/uploads/{ano}/{mes}/casos_obitos_doencas_preexistentes.csv'
            doencas = pd.read_csv(URL, sep=';', encoding='latin-1')

    try:
        print('\tAtualizando dados de casos/óbitos por raça e cor...')
        URL = ('https://raw.githubusercontent.com/seade-R/dados-covid-sp/master/data/casos_obitos_raca_cor.csv.zip')
        dados_raciais = pd.read_csv(URL, sep=';')
        opcoes_zip = dict(method='zip', archive_name='dados_raciais.csv')
        dados_raciais.to_csv('dados/dados_raciais.zip', sep=';', compression=opcoes_zip)
    except Exception as e:
        print(f'\tErro ao buscar dados_raciais.csv do GitHub: lendo arquivo local.\n\t{e}')
        dados_raciais = pd.read_csv('dados/dados_raciais.zip', sep=';', index_col=0)

    global vacinacao

    if vacinacao is True:
        print('\tAtualizando dados da campanha de vacinação...')

        headers = {'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                 'AppleWebKit/537.36 (KHTML, like Gecko) '
                                 'Chrome/88.0.4324.182 '
                                 'Safari/537.36 '
                                 'Edg/88.0.705.74'}

        try:
            print('\t\tDoses aplicadas por município...')
            URL = f'https://www.saopaulo.sp.gov.br/wp-content/uploads/{ano}/{mes}/{data}_vacinometro.csv'
            req = requests.get(URL, headers=headers, stream=True)
            req.encoding = req.apparent_encoding
            doses_aplicadas = pd.read_csv(StringIO(req.text), sep=';', encoding=req.encoding)
            if doses_aplicadas.columns.size == 1:
                raise Exception('Arquivo com problemas. Tentando buscar arquivo com final -1.csv...')
        except Exception as e:
            try:
                print('\t\tDoses recebidas por cada município...')
                URL = f'https://www.saopaulo.sp.gov.br/wp-content/uploads/{ano}/{mes}/{data}_vacinometro-1.csv'
                req = requests.get(URL, headers=headers, stream=True)
                req.encoding = req.apparent_encoding
                doses_aplicadas = pd.read_csv(StringIO(req.text), sep=';', encoding=req.encoding)
            except Exception as e:
                try:
                    print('\t\tDoses aplicadas por município... .csv.csv')
                    URL = f'https://www.saopaulo.sp.gov.br/wp-content/uploads/{ano}/{mes}/{data}_vacinometro.csv.csv'
                    req = requests.get(URL, headers=headers, stream=True)
                    req.encoding = req.apparent_encoding
                    doses_aplicadas = pd.read_csv(StringIO(req.text), sep=';', encoding=req.encoding)
                except Exception as e:
                    print(f'\t\tErro ao buscar {data}_vacinometro.csv da Seade: {e}')
                    doses_aplicadas = None

        try:
            print('\t\tDoses recebidas por cada município...')
            URL = f'https://www.saopaulo.sp.gov.br/wp-content/uploads/{ano}/{mes}/{data}_painel_distribuicao_doses.csv'
            req = requests.get(URL, headers=headers, stream=True)
            req.encoding = req.apparent_encoding
            doses_recebidas = pd.read_csv(StringIO(req.text), sep=';', encoding=req.encoding)
            if doses_recebidas.columns.size == 1:
                raise Exception('Arquivo com problemas. Tentando buscar arquivo com final -1.csv...')
        except Exception as e:
            try:
                print('\t\tDoses recebidas por cada município...')
                URL = f'https://www.saopaulo.sp.gov.br/wp-content/uploads/{ano}/{mes}/{data}_painel_distribuicao_doses-1.csv'
                req = requests.get(URL, headers=headers, stream=True)
                req.encoding = req.apparent_encoding
                doses_recebidas = pd.read_csv(StringIO(req.text), sep=';', encoding=req.encoding)
            except Exception as e:
                try:
                    print('\t\tDoses recebidas por cada município... .csv.csv')
                    URL = f'https://www.saopaulo.sp.gov.br/wp-content/uploads/{ano}/{mes}/{data}_painel_distribuicao_doses.csv.csv'
                    req = requests.get(URL, headers=headers, stream=True)
                    req.encoding = req.apparent_encoding
                    doses_recebidas = pd.read_csv(StringIO(req.text), sep=';', encoding=req.encoding)
                except Exception as e:
                    print(f'\t\tErro ao buscar {data}_painel_distribuicao_doses.csv da Seade: {e}')
                    doses_recebidas = None

        try:
            raise Exception('O scrapping do Tableau não funciona mais...')
            print('\t\tAtualizando doses aplicadas por vacina...')
            url = 'https://www2.simi.sp.gov.br/views/PaineldeEstatsticasGerais_14_09_2021_16316423974680/PaineldeEstatsticasGerais'
            scraper = TableauScraper()
            scraper.loads(url)
            sheet = scraper.getWorkbook().getWorksheet('donuts imunibiológico')
            atualizacao_imunizantes = sheet.data.copy()
            atualizacao_imunizantes['data'] = data_processamento
            atualizacao_imunizantes = atualizacao_imunizantes[['data', 'Imunobiologico -alias', 'SUM(Qtde)-alias']]
            atualizacao_imunizantes.columns = ['data', 'vacina', 'aplicadas']
            atualizacao_imunizantes = atualizacao_imunizantes.replace('ASTRAZENECA/OXFORD/FIOCRUZ', 'ASTRAZENECA | OXFORD', False)
            atualizacao_imunizantes = atualizacao_imunizantes.replace('CORONAVAC', 'CORONAVAC | BUTANTAN', False)
            atualizacao_imunizantes = atualizacao_imunizantes.replace('JANSSEN', 'JANSSEN | JOHNSON & JOHNSON', False)
            atualizacao_imunizantes = atualizacao_imunizantes.replace('PFIZER', 'PFIZER | BIONTECH', False)
            atualizacao_imunizantes.sort_values(by='vacina', inplace=True)
        except Exception as e:
            print(f'\t\tErro ao buscar dados de vacinas do Tableau: {e}')
            traceback.print_exception(type(e), e, e.__traceback__)
            atualizacao_imunizantes = None
    else:
        doses_aplicadas = None
        doses_recebidas = None
        atualizacao_imunizantes = None

    leitos_estaduais = pd.read_csv('dados/leitos_estaduais.csv', index_col=0)
    dados_vacinacao = pd.read_csv('dados/dados_vacinacao.zip')
    dados_imunizantes = pd.read_csv('dados/dados_imunizantes.csv')

    return dados_munic, dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, doses_aplicadas, doses_recebidas, dados_imunizantes, atualizacao_imunizantes


def pre_processamento(hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total, dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, doses_aplicadas, doses_recebidas, dados_munic, dados_imunizantes, atualizacao_imunizantes):
    print('\tDados municipais...')
    dados_cidade, hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total = pre_processamento_cidade(dados_munic, hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total)
    print('\tDados estaduais...')
    dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, dados_munic, dados_imunizantes = pre_processamento_estado(dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, doses_aplicadas, doses_recebidas, dados_munic, dados_imunizantes, atualizacao_imunizantes)

    return dados_cidade, dados_munic, hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total, dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, dados_imunizantes


def pre_processamento_cidade(dados_munic, hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total):
    dados_cidade = dados_munic.loc[dados_munic.nome_munic == 'São Paulo', ['datahora', 'casos', 'casos_novos', 'obitos', 'obitos_novos', 'letalidade']]
    dados_cidade.columns = ['data', 'confirmados', 'casos_dia', 'óbitos', 'óbitos_dia', 'letalidade']
    dados_cidade['letalidade'] = dados_cidade.letalidade * 100
    dados_cidade['data'] = pd.to_datetime(dados_cidade.data)
    dados_cidade['dia'] = dados_cidade.data.apply(lambda d: d.strftime('%d %b %y'))

    hospitais_campanha['data'] = pd.to_datetime(hospitais_campanha.data, format='%d/%m/%Y')
    hospitais_campanha['dia'] = hospitais_campanha.data.apply(lambda d: d.strftime('%d %b %y'))

    leitos_municipais['data'] = pd.to_datetime(leitos_municipais.data, format='%d/%m/%Y')
    leitos_municipais['dia'] = leitos_municipais.data.apply(lambda d: d.strftime('%d %b %y'))

    leitos_municipais_privados['data'] = pd.to_datetime(leitos_municipais_privados.data, format='%d/%m/%Y')
    leitos_municipais_privados['dia'] = leitos_municipais_privados.data.apply(lambda d: d.strftime('%d %b %y'))

    leitos_municipais_total['data'] = pd.to_datetime(leitos_municipais_total.data, format='%d/%m/%Y')
    leitos_municipais_total['dia'] = leitos_municipais_total.data.apply(lambda d: d.strftime('%d %b %y'))

    return dados_cidade, hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total


def formata_municipio(m):
    return m.title() \
        .replace(' Da ', ' da ') \
        .replace(' De ', ' de ') \
        .replace(' Do ', ' do ') \
        .replace(' Das ', ' das ') \
        .replace(' Dos ', ' dos ')


def pre_processamento_estado(dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, doses_aplicadas, doses_recebidas, dados_munic, dados_imunizantes, atualizacao_imunizantes):
    dados_estado.columns = ['data', 'total_casos', 'total_obitos']
    dados_estado['data'] = pd.to_datetime(dados_estado.data)
    dados_estado['dia'] = dados_estado.data.apply(lambda d: d.strftime('%d %b %y'))

    dados_munic['datahora'] = pd.to_datetime(dados_munic.datahora)

    isolamento['data'] = pd.to_datetime(isolamento.data)

    dias_faltantes = []
    data_atual = datetime.strptime('01/01/2021', '%d/%m/%Y')
    data_final = isolamento['data'].max()

    while data_atual.date() < data_final.date():
        if len(isolamento.loc[isolamento.data.dt.date == data_atual.date()]) == 0:
            dias_faltantes.append(data_atual.date())
        data_atual = data_atual + timedelta(days=1)

    dias_faltantes.append(data_processamento.date() - timedelta(days=1))

    tentativas = 0
    dados_atualizados = None

    def busca_isolamento():
        return False

        try:
            nonlocal dados_atualizados, tentativas, isolamento_atualizado
            tentativas = tentativas + 1
            print(f'\t\t{f"Tentativa {tentativas}: " if tentativas > 1 else ""}'
                  f'Atualizando dados de isolamento social...')
            URL = 'https://public.tableau.com/views/IsolamentoSocial/DADOS.csv?:showVizHome=no'
            dados_atualizados = pd.read_csv(URL, sep=',')
            return True
        except Exception:
            if tentativas <= 3:
                busca_isolamento()
            else:
                print('\t\tErro: não foi possível obter os dados atualizados de isolamento social.')
                return False

    if busca_isolamento():
        dados_atualizados.columns = ['codigo_ibge', 'data', 'município', 'populacao', 'UF', 'isolamento']
        dados_atualizados.drop(columns='codigo_ibge', inplace=True)

        for data in dias_faltantes:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            data_str = data.strftime('%A, %d/%m')
            isolamento_atualizado = dados_atualizados.loc[dados_atualizados.data == data_str].copy()
            locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

            if not isolamento_atualizado.empty and isolamento.loc[isolamento.data.dt.date == data, 'data'].empty:
                isolamento_atualizado['isolamento'] = pd.to_numeric(isolamento_atualizado.isolamento.str.replace('%', ''))
                isolamento_atualizado['município'] = isolamento_atualizado.município.apply(lambda m: formata_municipio(m))
                isolamento_atualizado['data'] = isolamento_atualizado.data.apply(
                    lambda d: datetime.strptime(d.split(', ')[1] + '/' + str(data.year), '%d/%m/%Y'))
                isolamento_atualizado['dia'] = isolamento_atualizado.data.apply(lambda d: d.strftime('%d %b %y'))

                isolamento = isolamento.append(isolamento_atualizado)
                isolamento['data'] = pd.to_datetime(isolamento.data)
                isolamento.sort_values(by=['data', 'isolamento'], inplace=True)
                isolamento.to_csv('dados/isolamento_social.csv', sep=',', index=False)

    print('\t\tAtualizando dados de internações...')
    leitos_estaduais['data'] = pd.to_datetime(leitos_estaduais.data, format='%d/%m/%Y')

    internacoes.columns = ['data', 'drs', 'pacientes_uti_mm7d', 'total_covid_uti_mm7d', 'ocupacao_leitos',
                           'pop', 'leitos_pc', 'internacoes_7d', 'internacoes_7d_l', 'internacoes_7v7',
                           'pacientes_uti_ultimo_dia', 'total_covid_uti_ultimo_dia', 'ocupacao_leitos_ultimo_dia',
                           'internacoes_ultimo_dia', 'pacientes_enf_mm7d', 'total_covid_enf_mm7d',
                           'pacientes_enf_ultimo_dia', 'total_covid_enf_ultimo_dia']

    internacoes['data'] = pd.to_datetime(internacoes.data)
    internacoes['dia'] = internacoes.data.apply(lambda d: d.strftime('%d %b %y'))

    if internacoes.data.max() > leitos_estaduais.data.max():
        novos_dados = {'data': internacoes.data.max(),
                       'sp_uti': None,
                       'sp_enfermaria': None,
                       'rmsp_uti': None,
                       'rmsp_enfermaria': None}

        leitos_estaduais = leitos_estaduais.append(novos_dados, ignore_index=True)

    def atualizaOcupacaoUTI(series):
        ocupacao = internacoes.loc[(internacoes.drs == 'Estado de São Paulo') & (internacoes.data == series['data']), 'ocupacao_leitos_ultimo_dia']
        series['sp_uti'] = ocupacao.item() if any(ocupacao) else series['sp_uti']

        leitos_enf = internacoes.loc[(internacoes.drs == 'Estado de São Paulo') & (internacoes.data == series['data']), 'total_covid_enf_ultimo_dia']

        if any(leitos_enf):
            pacientes_enf = internacoes.loc[(internacoes.drs == 'Estado de São Paulo') & (internacoes.data == series['data']), 'pacientes_enf_ultimo_dia']
            ocupacao = pacientes_enf.item() / leitos_enf.item()
            series['sp_enfermaria'] = round(ocupacao * 100, 2)

        filtro_drs = ((internacoes.drs.str.contains('SP')) | (internacoes.drs == 'Município de São Paulo'))
        leitos = internacoes.loc[(filtro_drs) & (internacoes.data == series['data']), 'total_covid_uti_ultimo_dia'].sum()

        if leitos > 0:
            pacientes = internacoes.loc[(filtro_drs) & (internacoes.data == series['data']), 'pacientes_uti_ultimo_dia'].sum()
            ocupacao = pacientes / leitos
            series['rmsp_uti'] = round(ocupacao * 100, 2)

        leitos_enf = internacoes.loc[(filtro_drs) & (internacoes.data == series['data']), 'total_covid_enf_ultimo_dia'].sum()

        if leitos_enf > 0:
            pacientes_enf = internacoes.loc[(filtro_drs) & (internacoes.data == series['data']), 'pacientes_enf_ultimo_dia'].sum()
            ocupacao = pacientes_enf / leitos_enf
            series['rmsp_enfermaria'] = round(ocupacao * 100, 2)

        return series

    leitos_estaduais = leitos_estaduais.apply(lambda linha: atualizaOcupacaoUTI(linha), axis=1)

    leitos_estaduais['dia'] = leitos_estaduais.data.apply(lambda d: d.strftime('%d %b %y'))
    leitos_estaduais['data'] = leitos_estaduais.data.apply(lambda d: d.strftime('%d/%m/%Y'))
    colunas = ['data', 'sp_uti', 'sp_enfermaria', 'rmsp_uti', 'rmsp_enfermaria']
    leitos_estaduais[colunas].to_csv('dados/leitos_estaduais.csv', sep=',')
    leitos_estaduais['data'] = pd.to_datetime(leitos_estaduais.data, format='%d/%m/%Y')

    print('\t\tAtualizando dados de doenças preexistentes...')

    doencas.columns = ['municipio', 'codigo_ibge', 'idade', 'sexo', 'covid19', 'data_inicio_sintomas', 'obito', 'asma',
                       'cardiopatia', 'diabetes', 'doenca_hematologica', 'doenca_hepatica', 'doenca_neurologica',
                       'doenca_renal', 'imunodepressao', 'obesidade', 'outros', 'pneumopatia', 'puerpera',
                       'sindrome_de_down']

    if processa_doencas:
        doencas = doencas.groupby(
            ['obito', 'covid19', 'idade', 'sexo', 'asma', 'cardiopatia', 'diabetes', 'doenca_hematologica',
             'doenca_hepatica', 'doenca_neurologica', 'doenca_renal', 'imunodepressao', 'obesidade', 'outros',
             'pneumopatia', 'puerpera', 'sindrome_de_down']) \
            .agg({'asma': 'count', 'cardiopatia': 'count', 'diabetes': 'count', 'doenca_hematologica': 'count',
                  'doenca_hepatica': 'count', 'doenca_neurologica': 'count', 'doenca_renal': 'count',
                  'imunodepressao': 'count', 'obesidade': 'count', 'outros': 'count', 'pneumopatia': 'count',
                  'puerpera': 'count', 'sindrome_de_down': 'count'})

    def calcula_letalidade(series):
        # localiza a linha atual passada como parâmetro e obtém a o índice da linha anterior
        indice = dados_estado.index[dados_estado.data == series['data']].item() - 1

        if indice >= 0:
            series['casos_dia'] = series['total_casos'] - dados_estado.loc[indice, 'total_casos']
            series['obitos_dia'] = series['total_obitos'] - dados_estado.loc[indice, 'total_obitos']
        else:
            series['casos_dia'] = series['total_casos']
            series['obitos_dia'] = series['total_obitos']

        # calcula a taxa de letalidade até a data atual
        if series['total_casos'] > 0:
            series['letalidade'] = round((series['total_obitos'] / series['total_casos']) * 100, 2)

        return series

    dados_estado = dados_estado.apply(lambda linha: calcula_letalidade(linha), axis=1)

    dados_raciais = dados_raciais[['obito', 'raca_cor']]
    dados_raciais = dados_raciais.fillna('IGNORADO')
    dados_raciais.loc[dados_raciais.raca_cor == 'NONE', 'raca_cor'] = 'IGNORADO'
    dados_raciais['raca_cor'] = dados_raciais.raca_cor.str.title()
    dados_raciais = dados_raciais.groupby(['obito', 'raca_cor']).agg(contagem=('obito', 'count'))

    def obtem_dado_anterior(municipio, coluna):
        indice = pd.Series(dtype='float64')
        dia_anterior = data_processamento - timedelta(days=1)

        data_inicio_vacinacao = dados_vacinacao.data.min().date()

        while indice.empty and dia_anterior.date() >= data_inicio_vacinacao:
            indice = dados_vacinacao.index[(dados_vacinacao.data.dt.date == dia_anterior.date()) &
                                           (dados_vacinacao.municipio == municipio)]
            dia_anterior = dia_anterior - timedelta(days=1)

        if not indice.empty:
            return dados_vacinacao.loc[indice.item(), coluna]

        return None if coluna != 'dose_unica' else 0

    def atualiza_doses(municipio):
        temp = doses_aplicadas.loc[doses_aplicadas['municipio'] == municipio]

        doses = temp.loc[temp.dose == '1º DOSE', 'contagem']
        primeira_dose = int(doses.iat[0]) if not doses.empty else None

        if primeira_dose is None:
            primeira_dose = obtem_dado_anterior(municipio, '1a_dose')

        doses = temp.loc[temp.dose == '2º DOSE', 'contagem']
        segunda_dose = int(doses.iat[0]) if not doses.empty else None

        if segunda_dose is None:
            segunda_dose = obtem_dado_anterior(municipio, '2a_dose')

        doses = temp.loc[temp.dose == '1º DOSE ADICIONAL', 'contagem']
        terceira_dose = int(doses.iat[0]) if not doses.empty else None

        if terceira_dose is None:
            terceira_dose = obtem_dado_anterior(municipio, '3a_dose')

        doses = temp.loc[temp.dose == '2º DOSE ADICIONAL', 'contagem']
        quarta_dose = int(doses.iat[0]) if not doses.empty else None

        if quarta_dose is None:
            quarta_dose = obtem_dado_anterior(municipio, '4a_dose')

        doses = temp.loc[temp.dose == '3º DOSE ADICIONAL', 'contagem']
        quinta_dose = int(doses.iat[0]) if not doses.empty else None

        if quinta_dose is None:
            quinta_dose = obtem_dado_anterior(municipio, '5a_dose')

        doses = temp.loc[temp.dose == '4º DOSE ADICIONAL', 'contagem']
        sexta_dose = int(doses.iat[0]) if not doses.empty else None

        if sexta_dose is None:
            sexta_dose = obtem_dado_anterior(municipio, '6a_dose')

        doses = temp.loc[(temp.dose == 'ÚNICA') | (temp.dose == 'UNICA'), 'contagem']
        dose_unica = int(doses.iat[0]) if not doses.empty else None

        if dose_unica is None:
            dose_unica = obtem_dado_anterior(municipio, 'dose_unica')

        if doses_recebidas is None:
            recebidas = obtem_dado_anterior(municipio, 'doses_recebidas')
        else:
            recebidas = doses_recebidas.loc[doses_recebidas.municipio == municipio, 'contagem']
            recebidas = None if recebidas.empty else recebidas.iat[0]

        nonlocal dados_vacinacao
        filtro = (dados_vacinacao.municipio == municipio) & (dados_vacinacao.data.dt.date == data_processamento.date())
        busca = dados_vacinacao.loc[filtro, 'municipio']

        if busca.empty:
            novos_dados = {'data': data_processamento,
                           'municipio': municipio,
                           'doses_recebidas': recebidas,
                           '1a_dose': primeira_dose,
                           '2a_dose': segunda_dose,
                           '3a_dose': terceira_dose,
                           '4a_dose': quarta_dose,
                           '5a_dose': quinta_dose,
                           '6a_dose': sexta_dose,
                           'dose_unica': dose_unica}

            dados_vacinacao = dados_vacinacao.append(novos_dados, ignore_index=True)
        else:
            dados_vacinacao.loc[filtro, 'doses_recebidas'] = recebidas
            dados_vacinacao.loc[filtro, '1a_dose'] = primeira_dose
            dados_vacinacao.loc[filtro, '2a_dose'] = segunda_dose
            dados_vacinacao.loc[filtro, '3a_dose'] = terceira_dose
            dados_vacinacao.loc[filtro, '4a_dose'] = quarta_dose
            dados_vacinacao.loc[filtro, '5a_dose'] = quinta_dose
            dados_vacinacao.loc[filtro, '6a_dose'] = sexta_dose
            dados_vacinacao.loc[filtro, 'dose_unica'] = dose_unica

    def atualiza_populacao():
        pop_cidade = internacoes.loc[(internacoes.drs == 'Município de São Paulo') &
                                     (internacoes.data == internacoes.data.max()), 'pop'].iat[0]

        if pop_cidade is not None:
            dados_vacinacao.loc[(dados_vacinacao.municipio == 'SAO PAULO') &
                                (dados_vacinacao.data.dt.date == data_processamento.date()), 'populacao'] = pop_cidade

    def atualiza_estado():
        if doses_aplicadas is None:
            return

        filtro_dose1 = (doses_aplicadas.dose == '1º DOSE') | (doses_aplicadas.dose == '1° DOSE')
        filtro_dose2 = (doses_aplicadas.dose == '2º DOSE') | (doses_aplicadas.dose == '2° DOSE')
        filtro_dose3 = (doses_aplicadas.dose == '3° DOSE') | (doses_aplicadas.dose == '1º DOSE ADICIONAL') | (doses_aplicadas.dose == '1° DOSE ADICIONAL')
        filtro_dose4 = (doses_aplicadas.dose == '4° DOSE') | (doses_aplicadas.dose == '2º DOSE ADICIONAL') | (doses_aplicadas.dose == '2° DOSE ADICIONAL')
        filtro_dose5 = (doses_aplicadas.dose == '5° DOSE') | (doses_aplicadas.dose == '3º DOSE ADICIONAL') | (doses_aplicadas.dose == '3° DOSE ADICIONAL')
        filtro_dose6 = (doses_aplicadas.dose == '6° DOSE') | (doses_aplicadas.dose == '4º DOSE ADICIONAL') | (doses_aplicadas.dose == '4° DOSE ADICIONAL')
        filtro_doseunica = (doses_aplicadas.dose == 'ÚNICA') | (doses_aplicadas.dose == 'UNICA')

        primeira_dose = doses_aplicadas.loc[filtro_dose1, 'contagem'].sum()

        if primeira_dose is None or primeira_dose == 0:
            primeira_dose = obtem_dado_anterior('ESTADO DE SAO PAULO', '1a_dose')

        segunda_dose = doses_aplicadas.loc[filtro_dose2, 'contagem'].sum()

        if segunda_dose is None or segunda_dose == 0:
            segunda_dose = obtem_dado_anterior('ESTADO DE SAO PAULO', '2a_dose')

        terceira_dose = doses_aplicadas.loc[filtro_dose3, 'contagem'].sum()

        if terceira_dose is None or terceira_dose == 0:
            terceira_dose = obtem_dado_anterior('ESTADO DE SAO PAULO', '3a_dose')

        quarta_dose = doses_aplicadas.loc[filtro_dose4, 'contagem'].sum()

        if quarta_dose is None or quarta_dose == 0:
            quarta_dose = obtem_dado_anterior('ESTADO DE SAO PAULO', '4a_dose')

        quinta_dose = doses_aplicadas.loc[filtro_dose5, 'contagem'].sum()

        if quinta_dose is None or quinta_dose == 0:
            quinta_dose = obtem_dado_anterior('ESTADO DE SAO PAULO', '5a_dose')

        sexta_dose = doses_aplicadas.loc[filtro_dose6, 'contagem'].sum()

        if sexta_dose is None or sexta_dose == 0:
            sexta_dose = obtem_dado_anterior('ESTADO DE SAO PAULO', '6a_dose')

        dose_unica = doses_aplicadas.loc[filtro_doseunica, 'contagem'].sum()

        if dose_unica is None or dose_unica == 0:
            dose_unica = obtem_dado_anterior('ESTADO DE SAO PAULO', 'dose_unica')

        if doses_recebidas is None:
            recebidas = obtem_dado_anterior('ESTADO DE SAO PAULO', 'doses_recebidas')
        else:
            recebidas = doses_recebidas['contagem'].sum()

        nonlocal dados_vacinacao
        filtro_e = dados_vacinacao.municipio == 'ESTADO DE SAO PAULO'
        filtro_d = dados_vacinacao.data.dt.date == data_processamento.date()

        busca = dados_vacinacao.loc[filtro_d & filtro_e, 'municipio']

        if busca.empty:
            novos_dados = {'data': data_processamento,
                           'municipio': 'ESTADO DE SAO PAULO',
                           'doses_recebidas': recebidas,
                           '1a_dose': primeira_dose,
                           '2a_dose': segunda_dose,
                           '3a_dose': terceira_dose,
                           '4a_dose': quarta_dose,
                           '5a_dose': quinta_dose,
                           '6a_dose': sexta_dose,
                           'dose_unica': dose_unica,
                           'populacao': internacoes.loc[(internacoes.drs == 'Estado de São Paulo') & (internacoes.data == internacoes.data.max()), 'pop'].iat[0]}

            dados_vacinacao = dados_vacinacao.append(novos_dados, ignore_index=True)
        else:
            dados_vacinacao.loc[filtro_d & filtro_e, 'doses_recebidas'] = recebidas
            dados_vacinacao.loc[filtro_d & filtro_e, '1a_dose'] = primeira_dose
            dados_vacinacao.loc[filtro_d & filtro_e, '2a_dose'] = segunda_dose
            dados_vacinacao.loc[filtro_d & filtro_e, '3a_dose'] = terceira_dose
            dados_vacinacao.loc[filtro_d & filtro_e, '4a_dose'] = quarta_dose
            dados_vacinacao.loc[filtro_d & filtro_e, '5a_dose'] = quinta_dose
            dados_vacinacao.loc[filtro_d & filtro_e, '6a_dose'] = sexta_dose
            dados_vacinacao.loc[filtro_d & filtro_e, 'dose_unica'] = dose_unica
            dados_vacinacao.loc[filtro_d & filtro_e, 'populacao'] = internacoes.loc[(internacoes.drs == 'Estado de São Paulo') & (internacoes.data == internacoes.data.max()), 'pop'].iat[0]

    def calcula_campos_adicionais(linha):
        primeira_dose = 0 if linha['1a_dose'] is None or isnan(linha['1a_dose']) else linha['1a_dose']
        segunda_dose = 0 if linha['2a_dose'] is None or isnan(linha['2a_dose']) else linha['2a_dose']
        terceira_dose = 0 if linha['3a_dose'] is None or isnan(linha['3a_dose']) else linha['3a_dose']
        quarta_dose = 0 if linha['4a_dose'] is None or isnan(linha['4a_dose']) else linha['4a_dose']
        quinta_dose = 0 if linha['5a_dose'] is None or isnan(linha['5a_dose']) else linha['5a_dose']
        sexta_dose = 0 if linha['6a_dose'] is None or isnan(linha['6a_dose']) else linha['6a_dose']
        dose_unica = 0 if linha['dose_unica'] is None or isnan(linha['dose_unica']) else linha['dose_unica']
        populacao = 0 if linha['populacao'] is None or isnan(linha['populacao']) else linha['populacao']
        doses_recebidas = 0 if linha['doses_recebidas'] is None or isnan(linha['doses_recebidas']) else linha['doses_recebidas']

        linha['total_doses'] = primeira_dose + segunda_dose + terceira_dose + quarta_dose + quinta_dose + sexta_dose + dose_unica

        try:
            linha['perc_vacinadas_1a_dose'] = (primeira_dose / populacao) * 100
        except Exception:
            linha['perc_vacinadas_1a_dose'] = None

        try:
            linha['perc_vacinadas_2a_dose'] = (segunda_dose / populacao) * 100
        except Exception:
            linha['perc_vacinadas_2a_dose'] = None

        try:
            linha['perc_vacinadas_3a_dose'] = (terceira_dose / populacao) * 100
        except Exception:
            linha['perc_vacinadas_3a_dose'] = None

        try:
            linha['perc_vacinadas_4a_dose'] = (quarta_dose / populacao) * 100
        except Exception:
            linha['perc_vacinadas_4a_dose'] = None

        try:
            linha['perc_vacinadas_5a_dose'] = (quinta_dose / populacao) * 100
        except Exception:
            linha['perc_vacinadas_5a_dose'] = None

        try:
            linha['perc_vacinadas_6a_dose'] = (sexta_dose / populacao) * 100
        except Exception:
            linha['perc_vacinadas_6a_dose'] = None

        try:
            linha['perc_vacinadas_dose_unica'] = (dose_unica / populacao) * 100
        except Exception:
            linha['perc_vacinadas_dose_unica'] = None

        try:
            linha['perc_vacinadas_1a_dose_dose_unica'] = ((primeira_dose + dose_unica) / populacao) * 100
        except Exception:
            linha['perc_vacinadas_1a_dose_dose_unica'] = None

        linha['perc_imunizadas'] = linha['perc_vacinadas_3a_dose']

        try:
            if doses_recebidas == 0:
                doses_recebidas = obtem_dado_anterior(linha['municipio'], 'doses_recebidas')

            linha['perc_aplicadas'] = (linha['total_doses'] / doses_recebidas) * 100
        except Exception:
            linha['perc_aplicadas'] = None

        total_doses_anterior = obtem_dado_anterior(linha['municipio'], 'total_doses')

        if total_doses_anterior is None:
            linha['aplicadas_dia'] = linha['total_doses']
        else:
            linha['aplicadas_dia'] = linha['total_doses'] - total_doses_anterior

        primeira_dose_anterior = obtem_dado_anterior(linha['municipio'], '1a_dose')

        if primeira_dose_anterior is None:
            linha['primeira_dose_dia'] = linha['1a_dose']
        else:
            linha['primeira_dose_dia'] = linha['1a_dose'] - primeira_dose_anterior

        segunda_dose_anterior = obtem_dado_anterior(linha['municipio'], '2a_dose')

        if segunda_dose_anterior is None:
            linha['segunda_dose_dia'] = linha['2a_dose']
        else:
            linha['segunda_dose_dia'] = linha['2a_dose'] - segunda_dose_anterior

        terceira_dose_anterior = obtem_dado_anterior(linha['municipio'], '3a_dose')

        if terceira_dose_anterior is None:
            linha['terceira_dose_dia'] = linha['3a_dose']
        else:
            linha['terceira_dose_dia'] = linha['3a_dose'] - terceira_dose_anterior

        quarta_dose_anterior = obtem_dado_anterior(linha['municipio'], '4a_dose')

        if quarta_dose_anterior is None:
            linha['quarta_dose_dia'] = linha['4a_dose']
        else:
            linha['quarta_dose_dia'] = linha['4a_dose'] - quarta_dose_anterior

        quinta_dose_anterior = obtem_dado_anterior(linha['municipio'], '5a_dose')

        if quinta_dose_anterior is None:
            linha['quinta_dose_dia'] = linha['5a_dose']
        else:
            linha['quinta_dose_dia'] = linha['5a_dose'] - quinta_dose_anterior

        sexta_dose_anterior = obtem_dado_anterior(linha['municipio'], '6a_dose')

        if sexta_dose_anterior is None:
            linha['sexta_dose_dia'] = linha['6a_dose']
        else:
            linha['sexta_dose_dia'] = linha['6a_dose'] - sexta_dose_anterior

        dose_unica_anterior = obtem_dado_anterior(linha['municipio'], 'dose_unica')

        if dose_unica_anterior is None:
            linha['dose_unica_dia'] = linha['dose_unica']
        else:
            linha['dose_unica_dia'] = linha['dose_unica'] - dose_unica_anterior

        return linha

    global vacinacao

    dados_vacinacao['data'] = pd.to_datetime(dados_vacinacao.data, format='%d/%m/%Y')

    if vacinacao is True:
        print('\t\tAtualizando dados da campanha de vacinação...')
        hoje = data_processamento

        dados_vacinacao['municipio'] = dados_vacinacao.municipio.apply(
            lambda m: ''.join(c for c in unicodedata.normalize('NFD', m.upper()) if unicodedata.category(c) != 'Mn'))

        if doses_recebidas is not None:
            doses_recebidas.columns = ['municipio', 'contagem']

            doses_recebidas['municipio'] = doses_recebidas.municipio.apply(lambda m: ''.join(c for c in unicodedata.normalize('NFD', m.upper()) if unicodedata.category(c) != 'Mn'))

        if doses_aplicadas is not None:
            try:
                doses_aplicadas.columns = ['municipio', 'dose', 'contagem']
            except ValueError as e:
                doses_aplicadas.columns = ['municipio', 'dose', 'municipio_repetido', 'drs', 'contagem']

            doses_aplicadas['dose'] = doses_aplicadas.dose.str.upper()
            doses_aplicadas['dose'] = doses_aplicadas.dose.str.replace('쨘', 'º')
            doses_aplicadas['dose'] = doses_aplicadas.dose.str.replace('횣', 'U')
            doses_aplicadas.loc[doses_aplicadas.municipio.str.contains('O PAULO'), 'municipio'] = 'SAO PAULO'
            doses_aplicadas['municipio'] = doses_aplicadas.municipio.apply(lambda m: ''.join(c for c in unicodedata.normalize('NFD', m.upper()) if unicodedata.category(c) != 'Mn'))

            print(f'\t\t\tAtualizando doses... {datetime.now():%H:%M:%S}')
            atualiza_doses('SAO PAULO')

            print(f'\t\t\tAtualizando população... {datetime.now():%H:%M:%S}')
            atualiza_populacao()

            print(f'\t\t\tAtualizando estado... {datetime.now():%H:%M:%S}')
            atualiza_estado()

            print(f'\t\t\tCalculando campos adicionais... {datetime.now():%H:%M:%S}')
            dados_vacinacao.loc[dados_vacinacao.data.dt.date == hoje.date()] = \
                dados_vacinacao.loc[dados_vacinacao.data.dt.date == hoje.date()].apply(lambda linha: calcula_campos_adicionais(linha), axis=1)

            print(f'\t\t\tOrdenando e salvando dados vacinação... {datetime.now():%H:%M:%S}')
            dados_vacinacao.sort_values(by=['data', 'municipio'], ascending=True, inplace=True)
            dados_vacinacao['data'] = dados_vacinacao.data.apply(lambda d: d.strftime('%d/%m/%Y'))
            opcoes_zip = dict(method='zip', archive_name='dados_vacinacao.csv')
            dados_vacinacao.to_csv('dados/dados_vacinacao.zip', index=False, compression=opcoes_zip)
            dados_vacinacao['data'] = pd.to_datetime(dados_vacinacao.data, format='%d/%m/%Y')

        print(f'\t\t\tAtualizando imunizantes... {datetime.now():%H:%M:%S}')
        dados_imunizantes['data'] = pd.to_datetime(dados_imunizantes.data, format='%d/%m/%Y')

        if atualizacao_imunizantes is not None:
            if dados_imunizantes.data.max().date() <= data_processamento.date():
                busca = dados_imunizantes.loc[dados_imunizantes.data.dt.date == data_processamento.date(), 'data']

                if busca.empty:
                    dados_imunizantes = dados_imunizantes.append(atualizacao_imunizantes)
                else:
                    for v in dados_imunizantes.vacina.unique():
                        dados_imunizantes.loc[(dados_imunizantes.data.dt.date == data_processamento.date()) & (dados_imunizantes.vacina == v), 'aplicadas'] = atualizacao_imunizantes.loc[(atualizacao_imunizantes.data.dt.date == data_processamento.date()) & (atualizacao_imunizantes.vacina == v), 'aplicadas'].iat[0]

                dados_imunizantes['data'] = dados_imunizantes['data'].apply(lambda d: d.strftime('%d/%m/%Y'))
                dados_imunizantes = dados_imunizantes.astype({'aplicadas': 'int32'})
                dados_imunizantes.to_csv('dados/dados_imunizantes.csv', index=False)
                dados_imunizantes['data'] = pd.to_datetime(dados_imunizantes.data, format='%d/%m/%Y')

    return dados_estado, isolamento, leitos_estaduais, internacoes, doencas, dados_raciais, dados_vacinacao, dados_munic, dados_imunizantes


def _converte_semana(data):
    convertion = data.strftime('%Y-W%U')

    if 'W00' in convertion:
        last_year = int(convertion.split('-')[0]) - 1
        convertion = pd.to_datetime('12-31-' + str(last_year)).strftime('%Y-W%U')

    return convertion


def _formata_semana_extenso(data, inclui_ano=True):
    # http://portalsinan.saude.gov.br/calendario-epidemiologico-2020
    if inclui_ano:
        return datetime.strptime(data + '-0', '%Y-W%U-%w').strftime('%d/%b/%y') + ' a ' + \
               datetime.strptime(data + '-6', '%Y-W%U-%w').strftime('%d/%b/%y')
    else:
        return datetime.strptime(data + '-0', '%Y-W%U-%w').strftime('%d/%b') + ' a ' + \
               datetime.strptime(data + '-6', '%Y-W%U-%w').strftime('%d/%b')


def gera_dados_evolucao_pandemia(dados_munic, dados_estado, isolamento, dados_vacinacao, internacoes):
    print('\tProcessando dados da evolução da pandemia...')
    # criar dataframe relação: comparar média de isolamento social de duas
    # semanas atrás com a quantidade de casos e de óbitos da semana atual
    isolamento['data_futuro'] = isolamento.data.apply(lambda d: d + timedelta(weeks=2))

    filtro = isolamento.município == 'Estado de São Paulo'
    colunas = ['data_futuro', 'isolamento']
    esquerda = isolamento.loc[filtro, colunas].groupby(['data_futuro']).mean().reset_index()
    esquerda.columns = ['data', 'isolamento']

    estado = dados_estado[['data', 'obitos_dia', 'casos_dia']].groupby(['data']).sum().reset_index()
    estado.columns = ['data', 'obitos_semana', 'casos_semana']

    estado = esquerda.merge(estado, on=['data'], how='outer', suffixes=('_isolamento', '_estado'))

    filtro = dados_vacinacao.municipio == 'ESTADO DE SAO PAULO'
    colunas = ['data', 'aplicadas_dia', 'perc_imunizadas']
    vacinacao = dados_vacinacao.loc[filtro, colunas].groupby(['data']).sum().reset_index()
    vacinacao.columns = ['data', 'vacinadas_semana', 'perc_imu_semana']

    estado = vacinacao.merge(estado, on=['data'], how='outer', suffixes=('_vacinacao', '_estado'))

    filtro = internacoes.drs == 'Estado de São Paulo'
    colunas = ['data', 'internacoes_ultimo_dia']
    intern = internacoes.loc[filtro, colunas].groupby(['data']).sum().reset_index()
    intern.columns = ['data', 'internacoes_semana']

    estado = intern.merge(estado, on=['data'], how='outer', suffixes=('_internacoes', '_estado'))

    estado['data'] = estado.data.apply(lambda d: _converte_semana(d))

    estado = estado.groupby('data') \
                   .agg({'isolamento': 'mean', 'obitos_semana': sum, 'casos_semana': sum,
                         'vacinadas_semana': sum, 'perc_imu_semana': max, 'internacoes_semana': sum}) \
                   .reset_index()

    estado['data'] = estado.data.apply(lambda d: _formata_semana_extenso(d))

    estado['casos_semana'] = estado.casos_semana.apply(lambda c: nan if c == 0 else c)
    estado['obitos_semana'] = estado.obitos_semana.apply(lambda c: nan if c == 0 else c)
    estado['vacinadas_semana'] = estado.vacinadas_semana.apply(lambda c: nan if c == 0 else c)
    estado['internacoes_semana'] = estado.internacoes_semana.apply(lambda c: nan if c == 0 else c)

    evolucao_estado = estado

    # dados municipais
    filtro = isolamento.município == 'São Paulo'
    colunas = ['data_futuro', 'isolamento']
    esquerda = isolamento.loc[filtro, colunas].groupby(['data_futuro']).mean().reset_index()
    esquerda.columns = ['data', 'isolamento']

    # cidade = dados_cidade[['data', 'óbitos_dia', 'casos_dia']].groupby(['data']).sum().reset_index()
    cidade = dados_munic.loc[dados_munic.nome_munic == 'São Paulo', ['datahora', 'obitos_novos', 'casos_novos']].groupby(['datahora']).sum().reset_index()
    cidade.columns = ['data', 'obitos_semana', 'casos_semana']

    cidade = esquerda.merge(cidade, on=['data'], how='outer', suffixes=('_isolamento', '_cidade'))

    filtro = dados_vacinacao.municipio == 'SAO PAULO'
    colunas = ['data', 'aplicadas_dia', 'perc_imunizadas']
    vacinacao = dados_vacinacao.loc[filtro, colunas].groupby(['data']).sum().reset_index()
    vacinacao.columns = ['data', 'vacinadas_semana', 'perc_imu_semana']

    cidade = vacinacao.merge(cidade, on=['data'], how='outer', suffixes=('_vacinacao', '_cidade'))

    filtro = ((internacoes.drs.str.contains('SP')) | (internacoes.drs == 'Município de São Paulo'))
    colunas = ['data', 'internacoes_ultimo_dia']
    intern = internacoes.loc[filtro, colunas].groupby(['data']).sum().reset_index()
    intern.columns = ['data', 'internacoes_semana']

    cidade = intern.merge(cidade, on=['data'], how='outer', suffixes=('_internacoes', '_estado'))

    cidade['data'] = cidade.data.apply(lambda d: _converte_semana(d))

    cidade = cidade.groupby('data') \
                   .agg({'isolamento': 'mean', 'obitos_semana': sum, 'casos_semana': sum,
                         'vacinadas_semana': sum, 'perc_imu_semana': max, 'internacoes_semana': sum}) \
                   .reset_index()

    cidade['data'] = cidade.data.apply(lambda d: _formata_semana_extenso(d))

    cidade['casos_semana'] = cidade.casos_semana.apply(lambda c: nan if c == 0 else c)
    cidade['obitos_semana'] = cidade.obitos_semana.apply(lambda c: nan if c == 0 else c)
    cidade['vacinadas_semana'] = cidade.vacinadas_semana.apply(lambda c: nan if c == 0 else c)
    estado['internacoes_semana'] = estado.internacoes_semana.apply(lambda c: nan if c == 0 else c)

    evolucao_cidade = cidade

    return evolucao_cidade, evolucao_estado


def gera_dados_semana(evolucao_cidade, evolucao_estado, leitos_estaduais, isolamento, internacoes):
    print('\tProcessando dados semanais...')

    def calcula_variacao(dados, linha):
        indice = dados.index[dados.data == linha['data']].item() - 1

        if indice >= 0:
            casos_anterior = dados.loc[indice, 'casos_semana']
            obitos_anterior = dados.loc[indice, 'obitos_semana']
            uti_anterior = dados.loc[indice, 'uti']
            isolamento_anterior = dados.loc[indice, 'isolamento_atual']
            isolamento_2sem_anterior = dados.loc[indice, 'isolamento']
            vacinadas_anterior = dados.loc[indice, 'vacinadas_semana']
            perc_imu_semana_anterior = dados.loc[indice, 'perc_imu_semana']
            internacoes_semana_anterior = dados.loc[indice, 'internacoes_semana']

            if casos_anterior > 0:
                linha['variacao_casos'] = ((linha['casos_semana'] / casos_anterior) - 1) * 100

            if obitos_anterior > 0:
                linha['variacao_obitos'] = ((linha['obitos_semana'] / obitos_anterior) - 1) * 100

            if uti_anterior > 0:
                linha['variacao_uti'] = ((linha['uti'] / uti_anterior) - 1) * 100

            if isolamento_anterior > 0:
                linha['variacao_isolamento'] = ((linha['isolamento_atual'] / isolamento_anterior) - 1) * 100

            if isolamento_2sem_anterior > 0:
                linha['variacao_isolamento_2sem'] = ((linha['isolamento'] / isolamento_2sem_anterior) - 1) * 100

            if vacinadas_anterior > 0:
                linha['variacao_vacinadas'] = ((linha['vacinadas_semana'] / vacinadas_anterior) - 1) * 100

            if perc_imu_semana_anterior > 0:
                linha['variacao_perc_imu'] = ((linha['perc_imu_semana'] / perc_imu_semana_anterior) - 1) * 100

            if internacoes_semana_anterior > 0:
                linha['variacao_internacoes'] = ((linha['internacoes_semana'] / internacoes_semana_anterior) - 1) * 100

        return linha

    # cálculo da média da taxa de ocupação de leitos de UTI na semana
    leitos = pd.DataFrame()
    leitos['data'] = internacoes.loc[internacoes.drs == 'Município de São Paulo', 'data'].apply(lambda d: _formata_semana_extenso(_converte_semana(d)))
    leitos['uti'] = internacoes.loc[internacoes.drs == 'Município de São Paulo', 'ocupacao_leitos_ultimo_dia']

    leitos = leitos.groupby('data').mean().reset_index()

    evolucao_cidade = evolucao_cidade.merge(leitos, on='data', how='outer', suffixes=('_efeito', '_leitos'))

    filtro = isolamento.município == 'São Paulo'
    colunas = ['data', 'isolamento']

    isola_atual = isolamento.loc[filtro, colunas]
    isola_atual['data'] = isola_atual.data.apply(lambda d: _formata_semana_extenso(_converte_semana(d)))
    isola_atual = isola_atual.groupby('data').mean().reset_index()
    isola_atual.columns = ['data', 'isolamento_atual']

    evolucao_cidade = evolucao_cidade.merge(isola_atual, on='data', how='left', suffixes=('_efeito', '_isola'))

    evolucao_cidade = evolucao_cidade.apply(lambda linha: calcula_variacao(evolucao_cidade, linha), axis=1)

    # dados estaduais
    leitos = pd.DataFrame()
    leitos['data'] = leitos_estaduais.data.apply(lambda d: _formata_semana_extenso(_converte_semana(d)))
    leitos['uti'] = leitos_estaduais.sp_uti

    leitos = leitos.groupby('data').mean().reset_index()

    evolucao_estado = evolucao_estado.merge(leitos, on='data', how='outer', suffixes=('_efeito', '_leitos'))

    filtro = isolamento.município == 'Estado de São Paulo'
    colunas = ['data', 'isolamento']

    isola_atual = isolamento.loc[filtro, colunas]
    isola_atual['data'] = isola_atual.data.apply(lambda d: _formata_semana_extenso(_converte_semana(d)))
    isola_atual = isola_atual.groupby('data').mean().reset_index()
    isola_atual.columns = ['data', 'isolamento_atual']

    evolucao_estado = evolucao_estado.merge(isola_atual, on='data', how='left', suffixes=('_efeito', '_isola'))

    evolucao_estado = evolucao_estado.apply(lambda linha: calcula_variacao(evolucao_estado, linha), axis=1)

    return evolucao_cidade, evolucao_estado


def gera_graficos(dados_munic, dados_cidade, hospitais_campanha, leitos_municipais, leitos_municipais_privados, leitos_municipais_total, dados_estado, isolamento, leitos_estaduais, evolucao_cidade, evolucao_estado, internacoes, doencas, dados_raciais, dados_vacinacao, dados_imunizantes):
    # print('\tResumo da campanha de vacinação...')
    # gera_resumo_vacinacao(dados_vacinacao)
    print('\tResumo diário...')
    gera_resumo_diario(dados_munic, dados_cidade, leitos_municipais_total, dados_estado, leitos_estaduais, isolamento, internacoes, dados_vacinacao)
    print('\tResumo semanal...')
    gera_resumo_semanal(evolucao_cidade, evolucao_estado)
    print('\tEvolução da pandemia no estado...')
    gera_evolucao_estado(evolucao_estado)
    print('\tEvolução da pandemia na cidade...')
    gera_evolucao_cidade(evolucao_cidade)
    print('\tCasos no estado...')
    gera_casos_estado(dados_estado)
    print('\tCasos na cidade...')
    gera_casos_cidade(dados_cidade)
    print('\tCasos e óbitos estaduais por raça/cor...')
    gera_casos_obitos_por_raca_cor(dados_raciais)
    print('\tIsolamento social...')
    gera_isolamento_grafico(isolamento)
    print('\tTabela de isolamento social...')
    gera_isolamento_tabela(isolamento)
    print('\tLeitos no estado...')
    gera_leitos_estaduais(leitos_estaduais)
    print('\tDepartamentos Regionais de Saúde...')
    gera_drs(internacoes)
    # print('\tEvolução da campanha de vacinação no estado...')
    # gera_evolucao_vacinacao_estado(dados_vacinacao)
    # print('\tEvolução da campanha de vacinação na cidade...')
    # gera_evolucao_vacinacao_cidade(dados_vacinacao)
    # print('\tPopulação vacinada...')
    # gera_populacao_vacinada(dados_vacinacao)
    # print('\t1ª dose x 2ª dose...')
    # gera_tipo_doses(dados_vacinacao)
    # print('\tDoses recebidas x aplicadas...')
    # gera_doses_aplicadas(dados_vacinacao)
    # print('\tTabela da campanha de vacinação...')
    # gera_tabela_vacinacao(dados_vacinacao)
    # print('\tDistribuição de imunizantes por fabricante...')
    # gera_distribuicao_imunizantes(dados_imunizantes)

    if processa_doencas:
        print('\tDoenças preexistentes nos casos estaduais...')
        gera_doencas_preexistentes_casos(doencas)
        print('\tDoenças preexistentes nos óbitos estaduais...')
        gera_doencas_preexistentes_obitos(doencas)


def gera_resumo_vacinacao(dados_vacinacao):
    filtro_data = dados_vacinacao.data.dt.date == data_processamento.date()
    filtro_data_max = dados_vacinacao.data == dados_vacinacao.data.max()
    filtro_estado = dados_vacinacao.municipio == 'ESTADO DE SAO PAULO'
    filtro_cidade = dados_vacinacao.municipio == 'SAO PAULO'
    inicio_vacinacao = pd.to_datetime('2021-01-17')

    cabecalho = ['<b>Campanha de<br>vacinação</b>',
                 '<b>Estado de SP</b><br><i>' + data_processamento.strftime('%d/%m/%Y') + '</i>',
                 '<b>Cidade de SP</b><br><i>' + data_processamento.strftime('%d/%m/%Y') + '</i>']

    info = ['<b>Doses aplicadas</b>', '<b>1ª dose</b>', '<b>2ª dose</b>', '<b>3ª dose</b>', '<b>4ª dose</b>',
            '<b>Dose única</b>', '<b>População 1ª dose (%)</b>', '<b>População 2ª dose (%)</b>',
            '<b>População 3ª dose (%)</b>', '<b>População 4ª dose (%)</b>', '<b>Média diária</b>',
            '<b>Média móvel 7 dias</b>', '<b>Média semanal</b>']

    doses_aplicadas = dados_vacinacao.loc[filtro_data & filtro_estado, 'total_doses']
    doses_aplicadas = 'indisponível' if doses_aplicadas.empty else f'{doses_aplicadas.item():7,.0f}'.replace(',', '.')

    dose_1 = dados_vacinacao.loc[filtro_data & filtro_estado, '1a_dose']
    dose_1 = 'indisponível' if dose_1.empty else f'{dose_1.item():7,.0f}'.replace(',', '.')

    dose_2 = dados_vacinacao.loc[filtro_data & filtro_estado, '2a_dose']
    dose_2 = 'indisponível' if dose_2.empty else f'{dose_2.item():7,.0f}'.replace(',', '.')

    dose_3 = dados_vacinacao.loc[filtro_data & filtro_estado, '3a_dose']
    dose_3 = 'indisponível' if dose_3.empty else f'{dose_3.item():7,.0f}'.replace(',', '.')

    dose_4 = dados_vacinacao.loc[filtro_data & filtro_estado, '4a_dose']
    dose_4 = 'indisponível' if dose_4.empty else f'{dose_4.item():7,.0f}'.replace(',', '.')

    dose_unica = dados_vacinacao.loc[filtro_data & filtro_estado, 'dose_unica']
    dose_unica = 'indisponível' if dose_unica.empty else f'{dose_unica.item():7,.0f}'.replace(',', '.')

    total_doses = dados_vacinacao.loc[filtro_data_max & filtro_estado, 'total_doses'].item()
    data_max = dados_vacinacao.loc[filtro_data_max & filtro_estado, 'data'].item()
    dias = (data_max - inicio_vacinacao).days + 1
    media_diaria = total_doses / dias
    media_diaria = f'{media_diaria:7,.0f}'.replace(',', '.')

    media_movel = dados_vacinacao.loc[filtro_estado, ['data', 'aplicadas_dia']] \
                                 .rolling('7D', on='data') \
                                 .mean() \
                                 .iat[-1,1]
    media_movel = f'{media_movel:7,.0f}'.replace(',', '.')

    semanas = dias / 7
    media_semanal = total_doses / semanas
    media_semanal = f'{media_semanal:7,.0f}'.replace(',', '.')

    pop_vacinada = dados_vacinacao.loc[filtro_data & filtro_estado, 'perc_vacinadas_1a_dose']
    pop_vacinada = 'indisponível' if pop_vacinada.empty else f'{pop_vacinada.item():7.2f}%'.replace('.', ',')

    pop_imunizada = dados_vacinacao.loc[filtro_data & filtro_estado, 'perc_vacinadas_2a_dose']
    pop_imunizada = 'indisponível' if pop_imunizada.empty else f'{pop_imunizada.item():7.2f}%'.replace('.', ',')

    pop_3doses = dados_vacinacao.loc[filtro_data & filtro_estado, 'perc_vacinadas_3a_dose']
    pop_3doses = 'indisponível' if pop_3doses.empty else f'{pop_3doses.item():7.2f}%'.replace('.', ',')

    pop_4doses = dados_vacinacao.loc[filtro_data & filtro_estado, 'perc_vacinadas_4a_dose']
    pop_4doses = 'indisponível' if pop_4doses.empty else f'{pop_4doses.item():7.2f}%'.replace('.', ',')

    estado = [doses_aplicadas,
              dose_1,
              dose_2,
              dose_3,
              dose_4,
              dose_unica,
              pop_vacinada,
              pop_imunizada,
              pop_3doses,
              pop_4doses,
              media_diaria,
              media_movel,
              media_semanal]

    doses_aplicadas = dados_vacinacao.loc[filtro_data & filtro_cidade, 'total_doses']
    doses_aplicadas = 'indisponível' if doses_aplicadas.empty else f'{doses_aplicadas.item():7,.0f}'.replace(',', '.')

    dose_1 = dados_vacinacao.loc[filtro_data & filtro_cidade, '1a_dose']
    dose_1 = 'indisponível' if dose_1.empty else f'{dose_1.item():7,.0f}'.replace(',', '.')

    dose_2 = dados_vacinacao.loc[filtro_data & filtro_cidade, '2a_dose']
    dose_2 = 'indisponível' if dose_2.empty else f'{dose_2.item():7,.0f}'.replace(',', '.') if not isnan(dose_2.item()) else 'indisponível'

    dose_3 = dados_vacinacao.loc[filtro_data & filtro_cidade, '3a_dose']
    dose_3 = 'indisponível' if dose_3.empty else f'{dose_3.item():7,.0f}'.replace(',', '.')

    dose_4 = dados_vacinacao.loc[filtro_data & filtro_cidade, '4a_dose']
    dose_4 = 'indisponível' if dose_4.empty else f'{dose_4.item():7,.0f}'.replace(',', '.')

    dose_unica = dados_vacinacao.loc[filtro_data & filtro_cidade, 'dose_unica']
    dose_unica = 'indisponível' if dose_unica.empty else f'{dose_unica.item():7,.0f}'.replace(',', '.')

    total_doses = dados_vacinacao.loc[filtro_data_max & filtro_cidade, 'total_doses'].item()
    data_max = dados_vacinacao.loc[filtro_data_max & filtro_cidade, 'data'].item()
    dias = (data_max - inicio_vacinacao).days
    media_diaria = total_doses / dias
    media_diaria = f'{media_diaria:7,.0f}'.replace(',', '.')

    media_movel = dados_vacinacao.loc[filtro_cidade, ['data', 'aplicadas_dia']] \
                                 .rolling('7D', on='data') \
                                 .mean() \
                                 .iat[-1,1]
    media_movel = f'{media_movel:7,.0f}'.replace(',', '.')

    semanas = dias / 7
    media_semanal = total_doses / semanas
    media_semanal = f'{media_semanal:7,.0f}'.replace(',', '.')

    pop_vacinada = dados_vacinacao.loc[filtro_data & filtro_cidade, 'perc_vacinadas_1a_dose']
    pop_vacinada = 'indisponível' if pop_vacinada.empty else f'{pop_vacinada.item():7.2f}%'.replace('.', ',')

    pop_imunizada = dados_vacinacao.loc[filtro_data & filtro_cidade, 'perc_vacinadas_2a_dose']
    pop_imunizada = 'indisponível' if pop_imunizada.empty else f'{pop_imunizada.item():7.2f}%'.replace('.', ',')

    pop_3doses = dados_vacinacao.loc[filtro_data & filtro_cidade, 'perc_vacinadas_3a_dose']
    pop_3doses = 'indisponível' if pop_3doses.empty else f'{pop_3doses.item():7.2f}%'.replace('.', ',')

    pop_4doses = dados_vacinacao.loc[filtro_data & filtro_cidade, 'perc_vacinadas_4a_dose']
    pop_4doses = 'indisponível' if pop_4doses.empty else f'{pop_4doses.item():7.2f}%'.replace('.', ',')

    cidade = [doses_aplicadas,
              dose_1,
              dose_2,
              dose_3,
              dose_4,
              dose_unica,
              pop_vacinada,
              pop_imunizada,
              pop_3doses,
              pop_4doses,
              media_diaria,
              media_movel,
              media_semanal]

    fig = go.Figure(data=[go.Table(header=dict(values=cabecalho,
                                               fill_color='#00aabb',
                                               font=dict(color='white'),
                                               align=['right', 'right', 'right'],
                                               line=dict(width=5)),
                                   cells=dict(values=[info, estado, cidade],
                                              fill_color='lavender',
                                              align='right',
                                              line=dict(width=5)),
                                   columnwidth=[1, 1, 1])])

    fig.update_layout(
        font=dict(size=15, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=30, pad=5),
        annotations=[dict(x=0, y=0, showarrow=False, font=dict(size=13),
                          text='<i><b>Fonte:</b> <a href = "https://www.seade.gov.br/coronavirus/">'
                               'Governo do Estado de São Paulo</a></i>')],
        height=550
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/resumo-vacinacao.html', include_plotlyjs='directory', auto_open=False)

    fig.update_layout(
        font=dict(size=13, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=30, pad=5),
        annotations=[dict(x=0, y=0)],
        height=620
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/resumo-vacinacao-mobile.html', include_plotlyjs='directory', auto_open=False)


def gera_resumo_diario(dados_munic, dados_cidade, leitos_municipais, dados_estado, leitos_estaduais, isolamento, internacoes, dados_vacinacao):
    hoje = data_processamento

    cabecalho = ['<b>Resumo diário</b>',
                 '<b>Estado de SP</b><br><i>' + hoje.strftime('%d/%m/%Y') + '</i>',
                 '<b>Cidade de SP</b><br><i>' + hoje.strftime('%d/%m/%Y') + '</i>']

    info = ['<b>Vacinadas</b>', '<b>Casos</b>', '<b>Casos no dia</b>', '<b>Óbitos</b>', '<b>Óbitos no dia</b>',
            '<b>Letalidade</b>', '<b>Leitos Covid-19</b>', '<b>Internados UTI</b>', '<b>Ocupação de UTIs</b>', '<b>Isolamento</b>']

    filtro = (isolamento.município == 'Estado de São Paulo') & (isolamento.data.dt.date == hoje.date() - timedelta(days=1))
    isolamento_atual = isolamento.loc[filtro, 'isolamento']
    isolamento_atual = 'indisponível' if isolamento_atual.empty else f'{isolamento_atual.item():7.0f}%'.replace('.', ',')

    filtro = (dados_vacinacao.municipio == 'ESTADO DE SAO PAULO') & (dados_vacinacao.data.dt.date == hoje.date())
    vacinadas = dados_vacinacao.loc[filtro, 'aplicadas_dia']
    vacinadas = 'indisponível' if vacinadas.empty else f'{vacinadas.item():7,.0f}'.replace(',', '.')

    filtro = (dados_estado.data.dt.date == hoje.date())

    total_casos = dados_estado.loc[filtro, 'total_casos']
    total_casos = 'indisponível' if total_casos.empty else f'{total_casos.item():7,.0f}'.replace(',', '.')

    casos_dia = dados_estado.loc[filtro, 'casos_dia']
    casos_dia = 'indisponível' if casos_dia.empty else f'{casos_dia.item():7,.0f}'.replace(',', '.')

    total_obitos = dados_estado.loc[filtro, 'total_obitos']
    total_obitos = 'indisponível' if total_obitos.empty else f'{total_obitos.item():7,.0f}'.replace(',', '.')

    obitos_dia = dados_estado.loc[filtro, 'obitos_dia']
    obitos_dia = 'indisponível' if obitos_dia.empty else f'{obitos_dia.item():7,.0f}'.replace(',', '.')

    letalidade_atual = dados_estado.loc[filtro, 'letalidade']
    letalidade_atual = 'indisponível' if letalidade_atual.empty else f'{letalidade_atual.item():7.2f}%'.replace('.', ',')

    leitos_covid = internacoes.loc[(internacoes.drs == 'Estado de São Paulo') & (internacoes.data.dt.date == hoje.date()), 'total_covid_uti_ultimo_dia']
    leitos_covid = 'indisponível' if leitos_covid.empty else f'{leitos_covid.item():7,.0f}'.replace(',', '.')

    internacoes_dia = internacoes.loc[(internacoes.drs == 'Estado de São Paulo') & (internacoes.data.dt.date == hoje.date()), 'pacientes_uti_ultimo_dia']
    internacoes_dia = 'indisponível' if internacoes_dia.empty else f'{internacoes_dia.item():7,.0f}'.replace(',', '.')

    ocupacao_uti = leitos_estaduais.loc[leitos_estaduais.data.dt.date == hoje.date(), 'sp_uti']
    ocupacao_uti = 'indisponível' if ocupacao_uti.empty else f'{ocupacao_uti.item():7.1f}%'.replace('.', ',')

    estado = [vacinadas,
              total_casos,
              casos_dia,
              total_obitos,
              obitos_dia,
              letalidade_atual,
              leitos_covid,
              internacoes_dia,
              ocupacao_uti,
              isolamento_atual]

    filtro = (isolamento.município == 'São Paulo') & (isolamento.data.dt.date == hoje.date() - timedelta(days=1))
    isolamento_atual = isolamento.loc[filtro, 'isolamento']
    isolamento_atual = 'indisponível' if isolamento_atual.empty else f'{isolamento_atual.item():7.0f}%'.replace('.', ',')

    filtro = (dados_vacinacao.municipio == 'SAO PAULO') & (dados_vacinacao.data.dt.date == hoje.date())
    vacinadas = dados_vacinacao.loc[filtro, 'aplicadas_dia']
    vacinadas = 'indisponível' if vacinadas.empty else f'{vacinadas.item():7,.0f}'.replace(',', '.')

    filtro = (dados_munic.nome_munic == 'São Paulo') & (dados_munic.datahora.dt.date == hoje.date())

    total_casos = dados_munic.loc[filtro, 'casos']
    total_casos = 'indisponível' if total_casos.empty else f'{total_casos.item():7,.0f}'.replace(',', '.')

    casos_dia = dados_munic.loc[filtro, 'casos_novos']
    casos_dia = 'indisponível' if casos_dia.empty else f'{casos_dia.item():7,.0f}'.replace(',', '.')

    total_obitos = dados_munic.loc[filtro, 'obitos']
    total_obitos = 'indisponível' if total_obitos.empty else f'{total_obitos.item():7,.0f}'.replace(',', '.')

    obitos_dia = dados_munic.loc[filtro, 'obitos_novos']
    obitos_dia = 'indisponível' if obitos_dia.empty else f'{obitos_dia.item():7,.0f}'.replace(',', '.')

    letalidade_atual = dados_munic.loc[filtro, 'letalidade']
    letalidade_atual = 'indisponível' if letalidade_atual.empty else f'{letalidade_atual.item() * 100:7.2f}%'.replace('.', ',')

    leitos_covid = internacoes.loc[(internacoes.drs == 'Município de São Paulo') & (internacoes.data.dt.date == hoje.date()), 'total_covid_uti_ultimo_dia']
    leitos_covid = 'indisponível' if leitos_covid.empty else f'{leitos_covid.item():7,.0f}'.replace(',', '.')

    internacoes_dia = internacoes.loc[(internacoes.drs == 'Município de São Paulo') & (internacoes.data.dt.date == hoje.date()), 'pacientes_uti_ultimo_dia']
    internacoes_dia = 'indisponível' if internacoes_dia.empty else f'{internacoes_dia.item():7,.0f}'.replace(',', '.')

    ocupacao_uti = internacoes.loc[(internacoes.drs == 'Município de São Paulo') & (internacoes.data.dt.date == hoje.date()), 'ocupacao_leitos_ultimo_dia']
    ocupacao_uti = 'indisponível' if ocupacao_uti.empty else f'{ocupacao_uti.item():7.1f}%'.replace('.', ',')

    cidade = [vacinadas,
              total_casos,
              casos_dia,
              total_obitos,
              obitos_dia,
              letalidade_atual,
              leitos_covid,
              internacoes_dia,
              ocupacao_uti,
              isolamento_atual]

    fig = go.Figure(data=[go.Table(header=dict(values=cabecalho,
                                               fill_color='#00aabb',
                                               font=dict(color='white'),
                                               align=['right', 'right', 'right'],
                                               line=dict(width=5)),
                                   cells=dict(values=[info, estado, cidade],
                                              fill_color='lavender',
                                              align='right',
                                              line=dict(width=5)),
                                   columnwidth=[1, 1, 1])])

    fig.update_layout(
        font=dict(size=15, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=30, pad=5),
        annotations=[dict(x=0, y=0, showarrow=False, font=dict(size=13),
                          text='<i><b>Fonte:</b> <a href = "https://www.seade.gov.br/coronavirus/">'
                               'Governo do Estado de São Paulo</a></i>')],
        height=445
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/resumo.html', include_plotlyjs='directory', auto_open=False)

    fig.update_layout(
        font=dict(size=13, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=30, pad=5),
        annotations=[dict(x=0, y=0)],
        height=430
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/resumo-mobile.html', include_plotlyjs='directory', auto_open=False)


def _formata_variacao(v, retorna_texto=False):
    if isnan(v) or v is None:
        if retorna_texto:
            return 'indisponível'
        else:
            return nan

    return f'+{v:02.1f}%'.replace('.', ',') if v >= 0 else f'{v:02.1f}%'.replace('.', ',')


def _formata_semana_ordinal(data):
    semana = int(f'{data:%W}')

    if semana == 0:
        last_year = data.year - 1
        data = pd.to_datetime('31/12/' + str(last_year), format='%d/%m/%Y')
        semana = int(data.strftime('%W'))

    return semana + 1 if data.year == 2020 else semana


def gera_resumo_semanal(evolucao_cidade, evolucao_estado):
    # %W: semana começa na segunda-feira
    hoje = data_processamento
    hoje_formatado = _formata_semana_ordinal(hoje)

    # %U: semana começa no domingo
    hoje = data_processamento - timedelta(days=1)
    semana = _formata_semana_extenso(_converte_semana(hoje), inclui_ano=False)

    cabecalho = [f'<b>{hoje_formatado}ª semana<br>epidemiológica</b>',
                 f'<b>Estado de SP</b><br>{semana}',
                 f'<b>Cidade de SP</b><br>{semana}']

    semana = _formata_semana_extenso(_converte_semana(hoje), inclui_ano=True)

    info = ['<b>Vacinadas</b>', '<b>Variação</b>',
            '<b>Casos</b>', '<b>Variação</b>',
            '<b>Óbitos</b>', '<b>Variação</b>',
            '<b>Internações</b>', '<b>Variação</b>',
            '<b>Ocupação de UTIs</b>', '<b>Variação</b>',
            '<b>Isolamento</b>', '<b>Variação</b>']

    num_semana = evolucao_estado.index[evolucao_estado.data == semana].item()

    vacinadas_semana = evolucao_estado.loc[num_semana, 'vacinadas_semana']
    vacinadas_semana = 'indisponível' if isnan(vacinadas_semana) else f'{vacinadas_semana.item():7,.0f}'.replace(',', '.')

    casos_semana = evolucao_estado.loc[num_semana, 'casos_semana']
    casos_semana = 'indisponível' if isnan(casos_semana) else f'{casos_semana.item():7,.0f}'.replace(',', '.')

    obitos_semana = evolucao_estado.loc[num_semana, 'obitos_semana']
    obitos_semana = 'indisponível' if isnan(obitos_semana) else f'{obitos_semana.item():7,.0f}'.replace(',', '.')

    internacoes = evolucao_estado.loc[num_semana, 'internacoes_semana']
    internacoes = 'indisponível' if isnan(internacoes) else f'{internacoes.item():7,.0f}'.replace(',', '.')

    uti = evolucao_estado.loc[num_semana, 'uti']
    uti = 'indisponível' if isnan(uti) else f'{uti.item():7.1f}%'.replace('.', ',')

    isolamento_atual = evolucao_estado.loc[num_semana, 'isolamento_atual']
    isolamento_atual = 'indisponível' if isnan(isolamento_atual) else f'{isolamento_atual.item():7.1f}%'.replace('.', ',')

    estado = [vacinadas_semana,  # Vacinadas
              '<i>' + _formata_variacao(evolucao_estado.loc[num_semana, 'variacao_vacinadas'], retorna_texto=True) + '</i>',  # Variação vacinadas
              casos_semana,  # Casos
              '<i>' + _formata_variacao(evolucao_estado.loc[num_semana, 'variacao_casos'], retorna_texto=True) + '</i>',  # Variação casos
              obitos_semana,  # óbitos
              '<i>' + _formata_variacao(evolucao_estado.loc[num_semana, 'variacao_obitos'], retorna_texto=True) + '</i>',  # Variação óbitos
              internacoes,  # Internações
              '<i>' + _formata_variacao(evolucao_estado.loc[num_semana, 'variacao_internacoes'], retorna_texto=True) + '</i>',  # Variação de internações
              uti,  # Ocupação de UTIs
              '<i>' + _formata_variacao(evolucao_estado.loc[num_semana, 'variacao_uti'], retorna_texto=True) + '</i>',  # Variação ocupação de UTIs
              isolamento_atual, # Isolamento social
              '<i>' + _formata_variacao(evolucao_estado.loc[num_semana, 'variacao_isolamento'], retorna_texto=True) + '</i>']  # Variação isolamento

    num_semana = evolucao_cidade.index[evolucao_cidade.data == semana].item()

    vacinadas_semana = evolucao_cidade.loc[num_semana, 'vacinadas_semana']
    vacinadas_semana = 'indisponível' if isnan(vacinadas_semana) else f'{vacinadas_semana.item():7,.0f}'.replace(',', '.')

    casos_semana = evolucao_cidade.loc[num_semana, 'casos_semana']
    casos_semana = 'indisponível' if isnan(casos_semana) else f'{casos_semana.item():7,.0f}'.replace(',', '.')

    obitos_semana = evolucao_cidade.loc[num_semana, 'obitos_semana']
    obitos_semana = 'indisponível' if isnan(obitos_semana) else f'{obitos_semana.item():7,.0f}'.replace(',', '.')

    internacoes = evolucao_cidade.loc[num_semana, 'internacoes_semana']
    internacoes = 'indisponível' if isnan(internacoes) else f'{internacoes.item():7,.0f}'.replace(',', '.')

    uti = evolucao_cidade.loc[num_semana, 'uti']
    uti = 'indisponível' if isnan(uti) else f'{uti.item():7.1f}%'.replace('.', ',')

    isolamento_atual = evolucao_cidade.loc[num_semana, 'isolamento_atual']
    isolamento_atual = 'indisponível' if isnan(isolamento_atual) else f'{isolamento_atual.item():7.1f}%'.replace('.', ',')

    cidade = [vacinadas_semana,  # Vacinadas
              '<i>' + _formata_variacao(evolucao_cidade.loc[num_semana, 'variacao_vacinadas'], retorna_texto=True) + '</i>',  # Variação vacinadas
              casos_semana,  # Casos
              '<i>' + _formata_variacao(evolucao_cidade.loc[num_semana, 'variacao_casos'], retorna_texto=True) + '</i>',  # Variação casos
              obitos_semana,  # óbitos
              '<i>' + _formata_variacao(evolucao_cidade.loc[num_semana, 'variacao_obitos'], retorna_texto=True) + '</i>',  # Variação óbitos
              internacoes,  # Internações
              '<i>' + _formata_variacao(evolucao_cidade.loc[num_semana, 'variacao_internacoes'], retorna_texto=True) + '</i>',  # Variação de internações
              uti,  # Ocupação de UTIs
              '<i>' + _formata_variacao(evolucao_cidade.loc[num_semana, 'variacao_uti'], retorna_texto=True) + '</i>',  # Variação ocupação de UTIs
              isolamento_atual,  # Isolamento social
              '<i>' + _formata_variacao(evolucao_cidade.loc[num_semana, 'variacao_isolamento'], retorna_texto=True) + '</i>']  # Variação isolamento

    fig = go.Figure(data=[go.Table(header=dict(values=cabecalho,
                                               fill_color='#00aabb',
                                               font=dict(color='white'),
                                               align=['right', 'right', 'right'],
                                               line=dict(width=5)),
                                   cells=dict(values=[info, estado, cidade],
                                              fill_color='lavender',
                                              align='right',
                                              line=dict(width=5)),
                                   columnwidth=[1, 1, 1])])

    fig.update_layout(
        font=dict(size=15, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=30, pad=5),
        annotations=[dict(x=0, y=0, showarrow=False, font=dict(size=13),
                          text='<i><b>Fonte:</b> <a href = "https://www.seade.gov.br/coronavirus/">'
                               'Governo do Estado de São Paulo</a></i>')],
        height=515
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/resumo-semanal.html', include_plotlyjs='directory', auto_open=False)

    fig.update_layout(
        font=dict(size=13, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=30, pad=5),
        annotations=[dict(x=0, y=0)],
        height=495
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/resumo-semanal-mobile.html', include_plotlyjs='directory', auto_open=False)


def gera_casos_estado(dados):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(x=dados['dia'], y=dados['total_casos'], line=dict(color='blue'),
                             mode='lines+markers', name='casos confirmados'))

    fig.add_trace(go.Bar(x=dados['dia'], y=dados['casos_dia'], marker_color='blue',
                         name='casos por dia'))

    fig.add_trace(go.Scatter(x=dados['dia'], y=dados['total_obitos'], line=dict(color='red'),
                             mode='lines+markers', name='total de óbitos'))

    fig.add_trace(go.Bar(x=dados['dia'], y=dados['obitos_dia'], marker_color='red',
                         name='óbitos por dia', visible='legendonly'))

    fig.add_trace(go.Scatter(x=dados['dia'], y=dados['letalidade'], line=dict(color='green'),
                             mode='lines+markers', name='letalidade', hovertemplate='%{y:.2f}%'),
                  secondary_y=True)

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Casos confirmados de Covid-19 no Estado de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        height=600
    )

    fig.update_yaxes(title_text='Número de casos ou óbitos', secondary_y=False)
    fig.update_yaxes(title_text='Taxa de letalidade (%)', secondary_y=True)

    # fig.show()

    pio.write_html(fig, file='docs/graficos/casos-estado.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(selector=dict(type='scatter'), mode='lines')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/casos-estado-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_casos_cidade(dados):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(x=dados['dia'], y=dados['confirmados'], line=dict(color='blue'),
                             mode='lines+markers', name='casos confirmados'))

    fig.add_trace(go.Bar(x=dados['dia'], y=dados['casos_dia'], marker_color='blue',
                         name='casos confirmados por dia'))

    fig.add_trace(go.Scatter(x=dados['dia'], y=dados['óbitos'], line=dict(color='red'),
                             mode='lines+markers', name='óbitos confirmados'))

    fig.add_trace(go.Bar(x=dados['dia'], y=dados['óbitos_dia'], marker_color='red',
                         name='óbitos confirmados por dia', visible='legendonly'))

    fig.add_trace(go.Scatter(x=dados['dia'], y=dados['letalidade'], line=dict(color='green'),
                             mode='lines+markers', name='letalidade', hovertemplate='%{y:.2f}%'),
                  secondary_y=True)

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Casos confirmados de Covid-19 na cidade de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        height=600
    )

    fig.update_yaxes(title_text='Número de casos ou óbitos', secondary_y=False)
    fig.update_yaxes(title_text='Taxa de letalidade (%)', secondary_y=True)

    # fig.show()

    pio.write_html(fig, file='docs/graficos/casos-cidade.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(selector=dict(type='scatter'), mode='lines')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=20),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/casos-cidade-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_doencas_preexistentes_casos(doencas):
    idades = list(doencas.reset_index('idade').idade.unique())

    casos_ignorados_m = [doencas.xs(('CONFIRMADO', 'FEMININO', i, 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO',
                                     'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO',
                                     'IGNORADO', 'IGNORADO'), level=('covid19', 'sexo', 'idade', 'asma', 'cardiopatia', 'diabetes', 'doenca_hematologica', 'doenca_hepatica',
                                     'doenca_neurologica', 'doenca_renal', 'imunodepressao', 'obesidade', 'outros', 'pneumopatia', 'puerpera',
                                     'sindrome_de_down')).asma.sum() for i in idades]
    casos_ignorados_h = [doencas.xs(('CONFIRMADO', 'MASCULINO', i, 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO',
                                     'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO',
                                     'IGNORADO', 'IGNORADO'), level=('covid19', 'sexo', 'idade', 'asma', 'cardiopatia', 'diabetes', 'doenca_hematologica', 'doenca_hepatica',
                                     'doenca_neurologica', 'doenca_renal', 'imunodepressao', 'obesidade', 'outros', 'pneumopatia', 'puerpera',
                                     'sindrome_de_down')).asma.sum() for i in idades]

    casos_sem_doencas_m = [doencas.xs(('CONFIRMADO', 'FEMININO', i, 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO',
                                       'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO'), level=('covid19', 'sexo', 'idade', 'asma', 'cardiopatia', 'diabetes', 'doenca_hematologica', 'doenca_hepatica',
                                       'doenca_neurologica', 'doenca_renal', 'imunodepressao', 'obesidade', 'outros', 'pneumopatia', 'puerpera',
                                       'sindrome_de_down')).asma.sum() for i in idades]
    casos_sem_doencas_h = [doencas.xs(('CONFIRMADO', 'MASCULINO', i, 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO',
                                       'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO'), level=('covid19', 'sexo', 'idade', 'asma', 'cardiopatia', 'diabetes', 'doenca_hematologica', 'doenca_hepatica',
                                       'doenca_neurologica', 'doenca_renal', 'imunodepressao', 'obesidade', 'outros', 'pneumopatia', 'puerpera',
                                       'sindrome_de_down')).asma.sum() for i in idades]

    casos_com_doencas_m = []
    casos_com_doencas_h = []

    for d in doencas.columns:
        casos_com_doencas_m.append(
            [doencas.xs(('CONFIRMADO', 'FEMININO', i, 'SIM'), level=('covid19', 'sexo', 'idade', d))[d].sum() for i in
             idades])
        casos_com_doencas_h.append(
            [doencas.xs(('CONFIRMADO', 'MASCULINO', i, 'SIM'), level=('covid19', 'sexo', 'idade', d))[d].sum() for i in
             idades])

    # para os dados femininos, todos os valores precisam ser negativados
    casos_ignorados_m_neg = [-valor for valor in casos_ignorados_m]
    casos_sem_doencas_m_neg = [-valor for valor in casos_sem_doencas_m]
    casos_com_doencas_m_neg = [[-valor for valor in lista] for lista in casos_com_doencas_m]

    if max(idades) < 10:
        idades = [i * 100 for i in idades]

    fig = go.Figure()

    cont = 0

    for lista_m in casos_com_doencas_m_neg:
        fig.add_trace(go.Bar(x=lista_m, y=idades, orientation='h',
                             hoverinfo='text+y+name', text=casos_com_doencas_m[cont],
                             marker_color='red', name=doencas.columns[cont], visible=True))
        cont = cont + 1

    cont = 0

    for lista_h in casos_com_doencas_h:
        fig.add_trace(go.Bar(x=lista_h, y=idades, orientation='h', hoverinfo='x+y+name',
                             marker_color='blue', name=doencas.columns[cont], visible=True))
        cont = cont + 1

    fig.add_trace(go.Bar(x=casos_sem_doencas_m_neg, y=idades, orientation='h',
                         hoverinfo='text+y+name', text=casos_sem_doencas_m,
                         marker_color='red', name='sem doenças<br>preexistentes', visible='legendonly'))

    fig.add_trace(go.Bar(x=casos_sem_doencas_h, y=idades, orientation='h', hoverinfo='x+y+name',
                         marker_color='blue', name='sem doenças<br>preexistentes', visible='legendonly'))

    fig.add_trace(go.Bar(x=casos_ignorados_m_neg, y=idades, orientation='h',
                         hoverinfo='text+y+name', text=casos_ignorados_m,
                         marker_color='red', name='ignorado', visible='legendonly'))

    fig.add_trace(go.Bar(x=casos_ignorados_h, y=idades, orientation='h', hoverinfo='x+y+name',
                         marker_color='blue', name='ignorado', visible='legendonly'))

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Doenças preexistentes nos casos confirmados de Covid-19 no Estado de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        yaxis_title='Idade',
        xaxis_title='Mulheres | Homens',
        hovermode='y',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        barmode='overlay',
        bargap=0.1,
        height=600
    )

    fig.update_yaxes(range=[0, 105], tickvals=[*range(0, 105, 5)])

    pio.write_html(fig, file='docs/graficos/doencas-casos.html', include_plotlyjs='directory',
                   auto_open=False, auto_play=False)

    # versão mobile
    fig.update_yaxes(range=[0, 105], tickvals=[*range(0, 105, 10)])

    fig.update_layout(
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    pio.write_html(fig, file='docs/graficos/doencas-casos-mobile.html', include_plotlyjs='directory',
                   auto_open=False, auto_play=False)


def gera_doencas_preexistentes_obitos(doencas):
    idades = list(doencas.reset_index('idade').idade.unique())

    obitos_ignorados_m = [doencas.xs(('CONFIRMADO', 'FEMININO', i, 1, 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO',
                                      'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO',
                                      'IGNORADO', 'IGNORADO', 'IGNORADO'), level=('covid19', 'sexo', 'idade', 'obito', 'asma', 'cardiopatia', 'diabetes', 'doenca_hematologica', 'doenca_hepatica',
                                      'doenca_neurologica', 'doenca_renal', 'imunodepressao', 'obesidade', 'outros', 'pneumopatia', 'puerpera',
                                      'sindrome_de_down')).asma.sum() for i in idades]
    obitos_ignorados_h = [doencas.xs(('CONFIRMADO', 'MASCULINO', i, 1, 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO',
                                      'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO', 'IGNORADO',
                                      'IGNORADO', 'IGNORADO', 'IGNORADO'), level=('covid19', 'sexo', 'idade', 'obito', 'asma', 'cardiopatia', 'diabetes', 'doenca_hematologica', 'doenca_hepatica',
                                      'doenca_neurologica', 'doenca_renal', 'imunodepressao', 'obesidade', 'outros', 'pneumopatia', 'puerpera',
                                      'sindrome_de_down')).asma.sum() for i in idades]

    obitos_sem_doencas_m = [doencas.xs(('CONFIRMADO', 'FEMININO', i, 1, 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO',
                                        'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO'), level=('covid19', 'sexo', 'idade', 'obito', 'asma', 'cardiopatia', 'diabetes', 'doenca_hematologica', 'doenca_hepatica',
                                        'doenca_neurologica', 'doenca_renal', 'imunodepressao', 'obesidade', 'outros', 'pneumopatia', 'puerpera',
                                        'sindrome_de_down')).asma.sum() for i in idades]
    obitos_sem_doencas_h = [doencas.xs(('CONFIRMADO', 'MASCULINO', i, 1, 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO',
                                       'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO', 'NÃO'), level=('covid19', 'sexo', 'idade', 'obito', 'asma', 'cardiopatia', 'diabetes', 'doenca_hematologica', 'doenca_hepatica',
                                       'doenca_neurologica', 'doenca_renal', 'imunodepressao', 'obesidade', 'outros', 'pneumopatia', 'puerpera',
                                       'sindrome_de_down')).asma.sum() for i in idades]

    obitos_com_doencas_m = []
    obitos_com_doencas_h = []

    for d in doencas.columns:
        obitos_com_doencas_m.append([doencas.xs(('CONFIRMADO', 'FEMININO', i, 1, 'SIM'),
                                                level=('covid19', 'sexo', 'idade', 'obito', d))[d].sum() for i in
                                     idades])
        obitos_com_doencas_h.append([doencas.xs(('CONFIRMADO', 'MASCULINO', i, 1, 'SIM'),
                                                level=('covid19', 'sexo', 'idade', 'obito', d))[d].sum() for i in
                                     idades])

    # para os dados femininos, todos os valores precisam ser negativados
    obitos_ignorados_m_neg = [-valor for valor in obitos_ignorados_m]
    obitos_sem_doencas_m_neg = [-valor for valor in obitos_sem_doencas_m]
    obitos_com_doencas_m_neg = [[-valor for valor in lista] for lista in obitos_com_doencas_m]

    if max(idades) < 10:
        idades = [i * 100 for i in idades]

    fig = go.Figure()

    cont = 0

    for lista_m in obitos_com_doencas_m_neg:
        fig.add_trace(go.Bar(x=lista_m, y=idades, orientation='h',
                             hoverinfo='text+y+name', text=obitos_com_doencas_m[cont],
                             marker_color='red', name=doencas.columns[cont], visible=True))
        cont = cont + 1

    cont = 0

    for lista_h in obitos_com_doencas_h:
        fig.add_trace(go.Bar(x=lista_h, y=idades, orientation='h', hoverinfo='x+y+name',
                             marker_color='blue', name=doencas.columns[cont], visible=True))
        cont = cont + 1

    fig.add_trace(go.Bar(x=obitos_sem_doencas_m_neg, y=idades, orientation='h',
                         hoverinfo='text+y+name', text=obitos_sem_doencas_m,
                         marker_color='red', name='sem doenças<br>preexistentes', visible='legendonly'))

    fig.add_trace(go.Bar(x=obitos_sem_doencas_h, y=idades, orientation='h', hoverinfo='x+y+name',
                         marker_color='blue', name='sem doenças<br>preexistentes', visible='legendonly'))

    fig.add_trace(go.Bar(x=obitos_ignorados_m_neg, y=idades, orientation='h',
                         hoverinfo='text+y+name', text=obitos_ignorados_m,
                         marker_color='red', name='ignorado', visible='legendonly'))

    fig.add_trace(go.Bar(x=obitos_ignorados_h, y=idades, orientation='h', hoverinfo='x+y+name',
                         marker_color='blue', name='ignorado', visible='legendonly'))

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Doenças preexistentes nos óbitos confirmados por Covid-19 no Estado de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        yaxis_title='Idade',
        xaxis_title='Mulheres | Homens',
        hovermode='y',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        barmode='overlay',
        bargap=0.1,
        height=600
    )

    fig.update_yaxes(range=[0, 105], tickvals=[*range(0, 105, 5)])

    pio.write_html(fig, file='docs/graficos/doencas-obitos.html', include_plotlyjs='directory',
                   auto_open=False, auto_play=False)

    # versão mobile
    fig.update_yaxes(range=[0, 105], tickvals=[*range(0, 105, 10)])

    fig.update_layout(
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    pio.write_html(fig, file='docs/graficos/doencas-obitos-mobile.html', include_plotlyjs='directory',
                   auto_open=False, auto_play=False)


def gera_casos_obitos_por_raca_cor(dados_raciais):
    racas_cores = list(dados_raciais.reset_index('raca_cor').raca_cor.unique())

    casos = [dados_raciais.xs(rc, level='raca_cor').contagem.sum() for rc in racas_cores]
    casos_perc = ['{:02.1f}%'.format((c / sum(casos)) * 100) for c in casos]

    obitos = [dados_raciais.xs((1, rc), level=('obito', 'raca_cor')).contagem.sum() for rc in racas_cores]
    obitos_perc = ['{:02.1f}%'.format((o / sum(obitos)) * 100) for o in obitos]

    fig = go.Figure()

    fig.add_trace(go.Bar(x=casos, y=racas_cores,
                         orientation='h', hoverinfo='x+y+name',
                         textposition='auto', text=casos_perc,
                         marker_color='blue', name='casos', visible=True))

    fig.add_trace(go.Bar(x=obitos, y=racas_cores,
                         orientation='h', hoverinfo='x+y+name',
                         textposition='auto', text=obitos_perc,
                         marker_color='red', name='óbitos', visible=True))

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Raça/cor nos casos e óbitos confirmados por Covid-19 no Estado de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        xaxis_title='Casos ou óbitos',
        xaxis_tickangle=30,
        hovermode='y',
        barmode='stack',
        bargap=0.1,
        hoverlabel={'namelength': -1},
        template='plotly',
        height=600
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/raca-cor.html', include_plotlyjs='directory',
                   auto_open=False, auto_play=False)

    # versão mobile
    fig.update_layout(
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    pio.write_html(fig, file='docs/graficos/raca-cor-mobile.html', include_plotlyjs='directory',
                   auto_open=False, auto_play=False)


def gera_isolamento_grafico(isolamento):
    fig = go.Figure()

    # lista de municípios em ordem de maior índice de isolamento
    l_municipios = list(
        isolamento.sort_values(by=['data', 'isolamento', 'município'], ascending=False).município.unique())

    # series em vez de list, para que seja possível utilizar o método isin
    s_municipios = pd.Series(l_municipios)

    titulo_a = 'Índice de adesão ao isolamento social - '
    titulo_b = '<br><i>Fonte: <a href = "https://www.saopaulo.sp.gov.br/coronavirus/isolamento/">Governo do Estado de São Paulo</a></i>'

    cidades_iniciais = ['Estado de São Paulo', 'São Paulo', 'Guarulhos', 'Osasco', 'Jundiaí', 'Caieiras',
                        'Campinas', 'Santo André', 'Mauá', 'Francisco Morato', 'Poá']

    for m in l_municipios:
        grafico = isolamento[isolamento.município == m]

        if m in cidades_iniciais:
            fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['isolamento'], name=m,
                                     mode='lines+markers', hovertemplate='%{y:.0f}%', visible=True))
        else:
            fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['isolamento'], name=m,
                                     mode='lines+markers+text', textposition='top center',
                                     text=grafico['isolamento'].apply(lambda i: str(i) + '%'),
                                     hovertemplate='%{y:.0f}%', visible=False))

    opcao_metro = dict(label='Região Metropolitana',
                       method='update',
                       args=[{'visible': s_municipios.isin(cidades_iniciais)},
                             {'title.text': titulo_a + 'Região Metropolitana' + titulo_b},
                             {'showlegend': True}])

    opcao_estado = dict(label='Estado de São Paulo',
                        method='update',
                        args=[{'visible': s_municipios.isin(['Estado de São Paulo'])},
                              {'title.text': titulo_a + 'Estado de São Paulo' + titulo_b},
                              {'showlegend': False}])

    def cria_lista_opcoes(cidade):
        return dict(label=cidade,
                    method='update',
                    args=[{'visible': s_municipios.isin([cidade])},
                          {'title.text': titulo_a + cidade + titulo_b},
                          {'showlegend': False}])

    fig.update_layout(
        font=dict(family='Roboto'),
        title=titulo_a + 'Região Metropolitana' + titulo_b,
        xaxis_tickangle=45,
        yaxis_title='Índice de isolamento social (%)',
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        updatemenus=[go.layout.Updatemenu(active=0,
                                          buttons=[opcao_metro, opcao_estado] + list(
                                              s_municipios.apply(lambda m: cria_lista_opcoes(m))),
                                          x=0.001, xanchor='left',
                                          y=0.990, yanchor='top')],
        height=600
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/isolamento.html', include_plotlyjs='directory', auto_open=False)

    # versão mobile
    fig.update_traces(mode='lines+text')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/isolamento-mobile.html', include_plotlyjs='directory', auto_open=False)


def gera_isolamento_tabela(isolamento):
    dados = isolamento.loc[isolamento.data == isolamento.data.max(), ['data', 'município', 'isolamento']]
    dados.sort_values(by=['isolamento', 'município'], ascending=False, inplace=True)

    cabecalho = ['<b>Cidade</b>',
                 '<b>Isolamento</b><br><i>' + dados.data.iloc[0].strftime('%d/%m/%Y') + '</i>']

    fig = go.Figure(data=[go.Table(header=dict(values=cabecalho,
                                               fill_color='#00aabb',
                                               font=dict(color='white'),
                                               align='right',
                                               line=dict(width=5)),
                                   cells=dict(values=[dados.município, dados.isolamento.map('{:02.0f}%'.format)],
                                              fill_color='lavender',
                                              align='right',
                                              line=dict(width=5),
                                              height=30),
                                   columnwidth=[1, 1])])

    fig.update_layout(
        font=dict(size=15, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=30, pad=5),
        annotations=[dict(x=0, y=1.05, showarrow=False, font=dict(size=13),
                          text='<i><b>Fonte:</b> <a href = "https://www.saopaulo.sp.gov.br/coronavirus/isolamento/">'
                               'Governo do Estado de São Paulo</a></i>')],
        height=600
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/tabela-isolamento.html', include_plotlyjs='directory', auto_open=False)

    fig.update_layout(
        font=dict(size=13, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=30, pad=5),
        annotations=[dict(x=0, y=1.05)],
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/tabela-isolamento-mobile.html', include_plotlyjs='directory',
                   auto_open=False)


def gera_evolucao_estado(evolucao_estado):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    grafico = evolucao_estado

    fig.add_trace(go.Scatter(x=grafico['data'], y=grafico['isolamento'], line=dict(color='orange'),
                             name='isolamento médio<br>de 2 semanas atrás', hovertemplate='%{y:.2f}%',
                             mode='lines+markers+text', textposition='top center',
                             text=grafico['variacao_isolamento_2sem'].apply(lambda v: _formata_variacao(v))),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=grafico['data'], y=grafico['uti'], line=dict(color='green'),
                             name='taxa média de<br>ocupação de UTI', hovertemplate='%{y:.2f}%',
                             mode='lines+markers+text', textposition='top center',
                             text=grafico['variacao_uti'].apply(lambda v: _formata_variacao(v))),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=grafico['data'], y=grafico['perc_imu_semana'], line=dict(color='black'),
                             name='população imunizada', hovertemplate='%{y:.2f}%',
                             mode='lines+markers+text', textposition='top center',
                             text=grafico['variacao_perc_imu'].apply(lambda v: _formata_variacao(v))),
                  secondary_y=True)

    fig.add_trace(go.Bar(x=grafico['data'], y=grafico['casos_semana'], marker_color='blue',
                         name='casos na<br>semana atual', textposition='outside',
                         text=grafico['variacao_casos'].apply(lambda v: _formata_variacao(v))))

    fig.add_trace(go.Bar(x=grafico['data'], y=grafico['obitos_semana'], marker_color='red',
                         name='óbitos na<br>semana atual', textposition='outside',
                         text=grafico['variacao_obitos'].apply(lambda v: _formata_variacao(v))))

    fig.add_trace(go.Bar(x=grafico['data'], y=grafico['vacinadas_semana'], visible='legendonly',
                         marker_color='black', textposition='outside', name='pessoas vacinadas<br>na semana atual',
                         text=grafico['variacao_vacinadas'].apply(lambda v: _formata_variacao(v))))

    fig.add_trace(go.Bar(x=grafico['data'], y=grafico['internacoes_semana'], visible='legendonly',
                         marker_color='green', textposition='outside', name='novas internações<br>na semana atual',
                         text=grafico['variacao_internacoes'].apply(lambda v: _formata_variacao(v))))

    d = grafico.data.size

    frames = [dict(data=[dict(type='scatter', x=grafico.data[:d + 1], y=grafico.isolamento[:d + 1]),
                         dict(type='scatter', x=grafico.data[:d + 1], y=grafico.uti[:d + 1]),
                         dict(type='scatter', x=grafico.data[:d + 1], y=grafico.perc_imu_semana[:d + 1]),
                         dict(type='bar', x=grafico.data[:d + 1], y=grafico.casos_semana[:d + 1]),
                         dict(type='bar', x=grafico.data[:d + 1], y=grafico.obitos_semana[:d + 1]),
                         dict(type='bar', x=grafico.data[:d + 1], y=grafico.vacinadas_semana[:d + 1]),
                         dict(type='bar', x=grafico.data[:d + 1], y=grafico.internacoes_semana[:d + 1])],
                   traces=[0, 1, 2, 3, 4, 5, 6],
                   ) for d in range(0, d)]

    fig.frames = frames

    botoes = [dict(label='Animar', method='animate',
                   args=[None, dict(frame=dict(duration=400, redraw=True), fromcurrent=True, mode='immediate')])]

    fig.update_yaxes(title_text='Número de casos ou óbitos', secondary_y=False)
    fig.update_yaxes(title_text='Taxa média de isolamento há 2 semanas (%)', secondary_y=True)

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Evolução da pandemia no Estado de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},
        template='plotly',
        updatemenus=[dict(type='buttons', showactive=False,
                          x=0.05, y=0.95,
                          xanchor='left', yanchor='top',
                          pad=dict(t=0, r=10), buttons=botoes)],
        height=600
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/evolucao-estado.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(selector=dict(type='scatter'), mode='lines')

    fig.update_xaxes(nticks=5)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/evolucao-estado-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_evolucao_cidade(evolucao_cidade):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    grafico = evolucao_cidade

    fig.add_trace(go.Scatter(x=grafico['data'], y=grafico['isolamento'], line=dict(color='orange'),
                             name='isolamento médio<br>de 2 semanas atrás', hovertemplate='%{y:.2f}%',
                             mode='lines+markers+text', textposition='top center',
                             text=grafico['variacao_isolamento_2sem'].apply(lambda v: _formata_variacao(v))),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=grafico['data'], y=grafico['uti'], line=dict(color='green'),
                             name='taxa média de<br>ocupação de UTI', hovertemplate='%{y:.2f}%',
                             mode='lines+markers+text', textposition='top center',
                             text=grafico['variacao_uti'].apply(lambda v: _formata_variacao(v))),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=grafico['data'], y=grafico['perc_imu_semana'], line=dict(color='black'),
                             name='população imunizada', hovertemplate='%{y:.2f}%',
                             mode='lines+markers+text', textposition='top center',
                             text=grafico['variacao_perc_imu'].apply(lambda v: _formata_variacao(v))),
                  secondary_y=True)

    fig.add_trace(go.Bar(x=grafico['data'], y=grafico['casos_semana'], marker_color='blue',
                         name='casos na<br>semana atual', textposition='outside',
                         text=grafico['variacao_casos'].apply(lambda v: _formata_variacao(v))))

    fig.add_trace(go.Bar(x=grafico['data'], y=grafico['obitos_semana'], marker_color='red',
                         name='óbitos na<br>semana atual', textposition='outside',
                         text=grafico['variacao_obitos'].apply(lambda v: _formata_variacao(v))))

    fig.add_trace(go.Bar(x=grafico['data'], y=grafico['vacinadas_semana'], visible='legendonly',
                         marker_color='black', textposition='outside', name='pessoas vacinadas<br>na semana atual',
                         text=grafico['variacao_vacinadas'].apply(lambda v: _formata_variacao(v))))

    fig.add_trace(go.Bar(x=grafico['data'], y=grafico['internacoes_semana'], visible='legendonly',
                         marker_color='green', textposition='outside', name='novas internações<br>na semana atual',
                         text=grafico['variacao_internacoes'].apply(lambda v: _formata_variacao(v))))

    d = grafico.data.size

    frames = [dict(data=[dict(type='scatter', x=grafico.data[:d + 1], y=grafico.isolamento[:d + 1]),
                         dict(type='scatter', x=grafico.data[:d + 1], y=grafico.uti[:d + 1]),
                         dict(type='scatter', x=grafico.data[:d + 1], y=grafico.perc_imu_semana[:d + 1]),
                         dict(type='bar', x=grafico.data[:d + 1], y=grafico.casos_semana[:d + 1]),
                         dict(type='bar', x=grafico.data[:d + 1], y=grafico.obitos_semana[:d + 1]),
                         dict(type='bar', x=grafico.data[:d + 1], y=grafico.vacinadas_semana[:d + 1]),
                         dict(type='bar', x=grafico.data[:d + 1], y=grafico.internacoes_semana[:d + 1])],
                   traces=[0, 1, 2, 3, 4, 5, 6],
                   ) for d in range(0, d)]

    fig.frames = frames

    botoes = [dict(label='Animar', method='animate',
                   args=[None, dict(frame=dict(duration=400, redraw=True), fromcurrent=True, mode='immediate')])]

    fig.update_yaxes(title_text='Número de casos ou óbitos', secondary_y=False)
    fig.update_yaxes(title_text='Taxa média de isolamento há 2 semanas (%)', secondary_y=True)

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Evolução da pandemia na Cidade de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},
        template='plotly',
        updatemenus=[dict(type='buttons', showactive=False,
                          x=0.05, y=0.95,
                          xanchor='left', yanchor='top',
                          pad=dict(t=0, r=10), buttons=botoes)],
        height=600
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/evolucao-cidade.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(selector=dict(type='scatter'), mode='lines')

    fig.update_xaxes(nticks=5)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/evolucao-cidade-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_leitos_estaduais(leitos):
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['rmsp_uti'],
                             mode='lines+markers', name='UTI<br>(região metropolitana)',
                             hovertemplate='%{y:.1f}%'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['rmsp_enfermaria'],
                             mode='lines+markers', name='enfermaria<br>(região metropolitana)',
                             hovertemplate='%{y:.1f}%'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['sp_uti'],
                             mode='lines+markers', name='UTI<br>(estado)', hovertemplate='%{y:.1f}%'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['sp_enfermaria'],
                             mode='lines+markers', name='enfermaria<br>(estado)', hovertemplate='%{y:.1f}%'))

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Ocupação de leitos Covid-19 no Estado de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle=45,
        yaxis_title='Taxa de ocupação dos leitos (%)',
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        height=600
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/leitos-estaduais.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(mode='lines')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/leitos-estaduais-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_drs(internacoes):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # lista de Departamentos Regionais de Saúde
    l_drs = list(internacoes.drs.sort_values(ascending=False).unique())

    # series em vez de list, para que seja possível utilizar o método isin
    s_drs = pd.Series(l_drs)

    titulo_a = 'Departamento Regional de Saúde - '
    titulo_b = '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">Governo do Estado de São Paulo</a></i>'

    for d in l_drs:
        grafico = internacoes[internacoes.drs == d]
        mostrar = d == 'Estado de São Paulo'

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['pacientes_uti_mm7d'],
                                 name='pacientes internados em leitos<br>de UTI para Covid-19 - média<br>móvel dos últimos 7 dias',
                                 mode='lines+markers', hovertemplate='%{y:.0f}', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['pacientes_uti_ultimo_dia'],
                                 name='pacientes internados em leitos<br>de UTI para Covid-19<br>no dia anterior',
                                 mode='lines+markers', hovertemplate='%{y:.0f}', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['total_covid_uti_mm7d'],
                                 name='leitos Covid-19 - média<br>móvel dos últimos 7 dias',
                                 mode='lines+markers', hovertemplate='%{y:.0f}', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['total_covid_uti_ultimo_dia'],
                                 name='leitos Covid-19<br>no dia anterior',
                                 mode='lines+markers', hovertemplate='%{y:.0f}', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['ocupacao_leitos'],
                                 name='ocupação de leitos de<br>UTI para Covid-19 - média<br>móvel dos últimos 7 dias',
                                 mode='lines+markers', hovertemplate='%{y:.2f}%', customdata=[d], visible=mostrar),
                      secondary_y=True)

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['ocupacao_leitos_ultimo_dia'],
                                 name='ocupação de leitos de<br>UTI para Covid-19<br>no dia anterior',
                                 mode='lines+markers', hovertemplate='%{y:.2f}%', customdata=[d], visible=mostrar),
                      secondary_y=True)

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['leitos_pc'], name='leitos Covid-19 para<br>cada 100 mil habitantes',
                                 mode='lines+markers', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['internacoes_7d'],
                                 name='internações (UTI e enfermaria,<br>confirmados e suspeitos)<br>média móvel dos últimos 7 dias',
                                 mode='lines+markers', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['internacoes_7d_l'],
                                 name='internações (UTI e enfermaria,<br>confirmados e suspeitos)<br>média móvel dos 7 dias<br>anteriores',
                                 mode='lines+markers', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['internacoes_7v7'],
                                 name='variação do número<br>de internações 7 dias',
                                 mode='lines+markers', hovertemplate='%{y:.1f}%', customdata=[d], visible=mostrar),
                      secondary_y=True)

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['internacoes_ultimo_dia'],
                                 name='internações (UTI e enfermaria,<br>confirmados e suspeitos)<br>no último dia',
                                 mode='lines+markers', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['pacientes_enf_mm7d'],
                                 name='pacientes enfermaria - <br>média móvel dos últimos 7 dias',
                                 mode='lines+markers', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['total_covid_enf_mm7d'],
                                 name='leitos enfermaria - <br>média móvel dos últimos 7 dias',
                                 mode='lines+markers', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['pacientes_enf_ultimo_dia'],
                                 name='pacientes em enfermaria<br>no último dia',
                                 mode='lines+markers', customdata=[d], visible=mostrar))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['total_covid_enf_ultimo_dia'],
                                 name='leitos de enfermaria<br>no último dia',
                                 mode='lines+markers', customdata=[d], visible=mostrar))

    def cria_lista_opcoes(drs):
        return dict(label=drs,
                    method='update',
                    args=[{'visible': [True if drs in trace['customdata'] else False for trace in fig._data]},
                          {'title.text': titulo_a + drs + titulo_b},
                          {'showlegend': True}])

    fig.update_layout(
        font=dict(family='Roboto'),
        title=titulo_a + 'Estado de São Paulo' + titulo_b,
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        updatemenus=[go.layout.Updatemenu(active=6,
                                          showactive=True,
                                          buttons=list(s_drs.apply(lambda d: cria_lista_opcoes(d))),
                                          x=0.001, xanchor='left',
                                          y=0.990, yanchor='top')],
        height=600
    )

    fig.update_yaxes(title_text='Número de leitos ou internações', secondary_y=False)
    fig.update_yaxes(title_text='Variação de internações (%)', secondary_y=True)

    # fig.show()

    pio.write_html(fig, file='docs/graficos/drs.html', include_plotlyjs='directory', auto_open=False)

    # versão mobile
    fig.update_traces(mode='lines+text')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/drs-mobile.html', include_plotlyjs='directory', auto_open=False)


def gera_leitos_municipais(leitos):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['ocupacao_uti_covid_publico'],
                             mode='lines+markers', name='taxa de ocupação de<br>leitos UTI Covid',
                             hovertemplate='%{y:.0f}%'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['uti_covid_publico'],
                             mode='lines+markers', name='leitos UTI Covid em operação'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['internados_uti_publico'],
                             mode='lines+markers', name='pacientes internados em<br>leitos UTI Covid'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['ventilacao_publico'], visible='legendonly',
                             mode='lines+markers', name='pacientes internados em<br>ventilação mecânica'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['internados_publico'], visible='legendonly',
                             mode='lines+markers', name='total de pacientes internados'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['respiratorio_publico'], visible='legendonly',
                             mode='lines+markers', name='pacientes atendidos com<br>quadro respiratório'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['suspeitos_publico'], visible='legendonly',
                             mode='lines+markers', name='pacientes atendidos com<br>suspeita de Covid-19'))

    d = leitos.dia.size

    frames = [dict(data=[dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.ocupacao_uti_covid_publico[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.uti_covid_publico[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.internados_uti_publico[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.ventilacao_publico[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.internados_publico[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.respiratorio_publico[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.suspeitos_publico[:d + 1])],
                   traces=[0, 1, 2, 3, 4, 5, 6],
                   ) for d in range(0, d)]

    fig.frames = frames

    botoes = [dict(label='Animar', method='animate',
                   args=[None, dict(frame=dict(duration=200, redraw=True), fromcurrent=True, mode='immediate')])]

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Situação dos 20 Hospitais Públicos Municipais' +
              '<br><i>Fonte: <a href = "https://www.prefeitura.sp.gov.br/cidade/' +
              'secretarias/saude/vigilancia_em_saude/doencas_e_agravos/coronavirus/' +
              'index.php?p=295572">Prefeitura de São Paulo</a></i>',
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        showlegend=True,
        updatemenus=[dict(type='buttons', showactive=False,
                          x=0.05, y=0.95,
                          xanchor='left', yanchor='top',
                          pad=dict(t=0, r=10), buttons=botoes)],
        height=600
    )

    fig.update_yaxes(title_text='Número de pacientes', secondary_y=False)
    fig.update_yaxes(title_text='Taxa de ocupação de UTI (%)', secondary_y=True)

    # fig.show()

    pio.write_html(fig, file='docs/graficos/leitos-municipais.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(mode='lines')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=20),
        showlegend=False,
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/leitos-municipais-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_leitos_municipais_privados(leitos):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['ocupacao_uti_covid_privado'],
                             mode='lines+markers', name='taxa de ocupação de<br>leitos UTI Covid',
                             hovertemplate='%{y:.0f}%'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['uti_covid_privado'],
                             mode='lines+markers', name='leitos UTI Covid em operação'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['internados_uti_privado'],
                             mode='lines+markers', name='pacientes internados em<br>leitos UTI Covid'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['ventilacao_privado'], visible='legendonly',
                             mode='lines+markers', name='pacientes internados em<br>ventilação mecânica'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['internados_privado'], visible='legendonly',
                             mode='lines+markers', name='total de pacientes internados'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['respiratorio_privado'], visible='legendonly',
                             mode='lines+markers', name='pacientes atendidos com<br>quadro respiratório'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['suspeitos_privado'], visible='legendonly',
                             mode='lines+markers', name='pacientes atendidos com<br>suspeita de Covid-19'))

    d = leitos.dia.size

    frames = [dict(data=[dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.ocupacao_uti_covid_privado[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.uti_covid_privado[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.internados_uti_privado[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.ventilacao_privado[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.internados_privado[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.respiratorio_privado[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.suspeitos_privado[:d + 1])],
                   traces=[0, 1, 2, 3, 4, 5, 6],
                   ) for d in range(0, d)]

    fig.frames = frames

    botoes = [dict(label='Animar', method='animate',
                   args=[None, dict(frame=dict(duration=200, redraw=True), fromcurrent=True, mode='immediate')])]

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Situação dos leitos privados contratados pela Prefeitura' +
              '<br><i>Fonte: <a href = "https://www.prefeitura.sp.gov.br/cidade/' +
              'secretarias/saude/vigilancia_em_saude/doencas_e_agravos/coronavirus/' +
              'index.php?p=295572">Prefeitura de São Paulo</a></i>',
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        showlegend=True,
        updatemenus=[dict(type='buttons', showactive=False,
                          x=0.05, y=0.95,
                          xanchor='left', yanchor='top',
                          pad=dict(t=0, r=10), buttons=botoes)],
        height=600
    )

    fig.update_yaxes(title_text='Número de pacientes', secondary_y=False)
    fig.update_yaxes(title_text='Taxa de ocupação de UTI (%)', secondary_y=True)

    # fig.show()

    pio.write_html(fig, file='docs/graficos/leitos-municipais-privados.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(mode='lines')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=20),
        showlegend=False,
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/leitos-municipais-privados-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_leitos_municipais_total(leitos):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['ocupacao_uti_covid_total'],
                             mode='lines+markers', name='taxa de ocupação de<br>leitos UTI Covid',
                             hovertemplate='%{y:.0f}%'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['uti_covid_total'],
                             mode='lines+markers', name='leitos UTI Covid em operação'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['internados_uti_total'],
                             mode='lines+markers', name='pacientes internados em<br>leitos UTI Covid'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['ventilacao_total'], visible='legendonly',
                             mode='lines+markers', name='pacientes internados em<br>ventilação mecânica'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['internados_total'], visible='legendonly',
                             mode='lines+markers', name='total de pacientes internados'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['respiratorio_total'], visible='legendonly',
                             mode='lines+markers', name='pacientes atendidos com<br>quadro respiratório'))

    fig.add_trace(go.Scatter(x=leitos['dia'], y=leitos['suspeitos_total'], visible='legendonly',
                             mode='lines+markers', name='pacientes atendidos com<br>suspeita de Covid-19'))

    d = leitos.dia.size

    frames = [dict(data=[dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.ocupacao_uti_covid_total[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.uti_covid_total[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.internados_uti_total[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.ventilacao_total[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.internados_total[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.respiratorio_total[:d + 1]),
                         dict(type='scatter', x=leitos.dia[:d + 1], y=leitos.suspeitos_total[:d + 1])],
                   traces=[0, 1, 2, 3, 4, 5, 6],
                   ) for d in range(0, d)]

    fig.frames = frames

    botoes = [dict(label='Animar', method='animate',
                   args=[None, dict(frame=dict(duration=200, redraw=True), fromcurrent=True, mode='immediate')])]

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Situação geral dos leitos públicos e privados' +
              '<br><i>Fonte: <a href = "https://www.prefeitura.sp.gov.br/cidade/' +
              'secretarias/saude/vigilancia_em_saude/doencas_e_agravos/coronavirus/' +
              'index.php?p=295572">Prefeitura de São Paulo</a></i>',
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        showlegend=True,
        updatemenus=[dict(type='buttons', showactive=False,
                          x=0.05, y=0.95,
                          xanchor='left', yanchor='top',
                          pad=dict(t=0, r=10), buttons=botoes)],
        height=600
    )

    fig.update_yaxes(title_text='Número de pacientes', secondary_y=False)
    fig.update_yaxes(title_text='Taxa de ocupação de UTI (%)', secondary_y=True)

    # fig.show()

    pio.write_html(fig, file='docs/graficos/leitos-municipais-total.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(mode='lines')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=20),
        showlegend=False,
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/leitos-municipais-total-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_hospitais_campanha(hospitais_campanha):
    for h in hospitais_campanha.hospital.unique():
        grafico = hospitais_campanha[hospitais_campanha.hospital == h]

        fig = go.Figure()

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['comum'],
                                 mode='lines+markers', name='leitos de enfermaria'))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['ocupação_comum'],
                                 mode='lines+markers', name='internados em leitos<br>de enfermaria'))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['uti'],
                                 mode='lines+markers', name='leitos de estabilização'))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['ocupação_uti'],
                                 mode='lines+markers', name='internados em leitos<br>de estabilização'))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['altas'],
                                 mode='lines+markers', name='altas', visible='legendonly'))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['óbitos'],
                                 mode='lines+markers', name='óbitos', visible='legendonly'))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['transferidos'],
                                 mode='lines+markers', name='transferidos para Hospitais<br>após agravamento clínico',
                                 visible='legendonly'))

        fig.add_trace(go.Scatter(x=grafico['dia'], y=grafico['chegando'],
                                 mode='lines+markers',
                                 name='pacientes em processo de<br>transferência para internação<br>no HMCamp',
                                 visible='legendonly'))

        d = grafico.dia.size

        frames = [dict(data=[dict(type='scatter', x=grafico.dia[:d + 1], y=grafico.comum[:d + 1]),
                             dict(type='scatter', x=grafico.dia[:d + 1], y=grafico.ocupação_comum[:d + 1]),
                             dict(type='scatter', x=grafico.dia[:d + 1], y=grafico.uti[:d + 1]),
                             dict(type='scatter', x=grafico.dia[:d + 1], y=grafico.ocupação_uti[:d + 1]),
                             dict(type='scatter', x=grafico.dia[:d + 1], y=grafico.altas[:d + 1]),
                             dict(type='scatter', x=grafico.dia[:d + 1], y=grafico.óbitos[:d + 1]),
                             dict(type='scatter', x=grafico.dia[:d + 1], y=grafico.transferidos[:d + 1]),
                             dict(type='scatter', x=grafico.dia[:d + 1], y=grafico.chegando[:d + 1])],
                       traces=[0, 1, 2, 3, 4, 5, 6, 7],
                       ) for d in range(0, d)]

        fig.frames = frames

        botoes = [dict(label='Animar', method='animate',
                       args=[None, dict(frame=dict(duration=200, redraw=True), fromcurrent=True, mode='immediate')])]

        fig.update_layout(
            font=dict(family='Roboto'),
            title='Ocupação dos leitos do HMCamp ' + h +
                  '<br><i>Fonte: <a href = "https://www.prefeitura.sp.gov.br/cidade/' +
                  'secretarias/saude/vigilancia_em_saude/doencas_e_agravos/coronavirus/' +
                  'index.php?p=295572">Prefeitura de São Paulo</a></i>',
            xaxis_tickangle=45,
            yaxis_title='Número de leitos ou pacientes',
            hovermode='x unified',
            hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
            template='plotly',
            updatemenus=[dict(type='buttons', showactive=False,
                              x=0.05, y=0.95,
                              xanchor='left', yanchor='top',
                              pad=dict(t=0, r=10), buttons=botoes)],
            height=600
        )

        # fig.show()

        pio.write_html(fig, file='docs/graficos/' + h.lower() + '.html',
                       include_plotlyjs='directory', auto_open=False, auto_play=False)

        # versão mobile
        fig.update_traces(mode='lines')

        fig.update_xaxes(nticks=10)

        fig.update_layout(
            showlegend=False,
            font=dict(size=11, family='Roboto'),
            margin=dict(l=1, r=1, b=1, t=90, pad=20),
            height=400
        )

        # fig.show()

        pio.write_html(fig, file='docs/graficos/' + h.lower() + '-mobile.html',
                       include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_evolucao_vacinacao_estado(dados_vacinacao):
    dados = dados_vacinacao.loc[dados_vacinacao.municipio == 'ESTADO DE SAO PAULO'].copy()
    dados = dados[1:]

    media_movel = dados.loc[:, ['data', 'aplicadas_dia']].rolling('7D', on='data').mean()
    media_movel['data'] = media_movel.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    dados['data'] = dados.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['total_doses'], line=dict(color='purple'),
                             mode='lines+markers', name='doses aplicadas', visible='legendonly'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['primeira_dose_dia'], marker_color='blue',
                         name='doses aplicadas<br>por dia (1ª dose)'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['segunda_dose_dia'], marker_color='green',
                         name='doses aplicadas<br>por dia (2ª dose)'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['terceira_dose_dia'], name='doses aplicadas<br>por dia (3ª dose)'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['quarta_dose_dia'], name='doses aplicadas<br>por dia (4ª dose)'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['dose_unica_dia'], name='doses aplicadas<br>por dia (dose única)'))

    fig.add_trace(go.Scatter(x=media_movel['data'], y=media_movel['aplicadas_dia'], line=dict(color='red'),
                             mode='lines+markers', name='média móvel de doses<br>aplicadas em 7 dias'))

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_1a_dose'], line=dict(color='orange'),
                             mode='lines+markers', name='população vacinada<br>1ª dose',
                             hovertemplate='%{y:.2f}%'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_2a_dose'], line=dict(color='goldenrod'),
                             mode='lines+markers', name='população vacinada<br>2ª dose',
                             hovertemplate='%{y:.2f}%', visible='legendonly'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_dose_unica'], mode='lines+markers',
                             name='população vacinada<br>dose única',
                             hovertemplate='%{y:.2f}%', visible='legendonly'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_3a_dose'], mode='lines+markers',
                             name='população vacinada<br>com a 3ª dose',
                             hovertemplate='%{y:.2f}%', visible='legendonly'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_4a_dose'], mode='lines+markers',
                             name='população vacinada<br>com a 4ª dose',
                             hovertemplate='%{y:.2f}%', visible='legendonly'),
                  secondary_y=True)

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Evolução da vacinação no Estado de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        barmode='stack',
        height=600
    )

    fig.update_yaxes(title_text='Doses aplicadas', secondary_y=False)
    fig.update_yaxes(title_text='População vacinada (%)', secondary_y=True)

    # fig.show()

    pio.write_html(fig, file='docs/graficos/vacinacao-estado.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(selector=dict(type='scatter'), mode='lines')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/vacinacao-estado-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_evolucao_vacinacao_cidade(dados_vacinacao):
    dados = dados_vacinacao.loc[dados_vacinacao.municipio == 'SAO PAULO'].copy()
    dados = dados[1:]

    media_movel = dados.loc[:, ['data', 'aplicadas_dia']].rolling('7D', on='data').mean()
    media_movel['data'] = dados.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    dados['data'] = dados.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['total_doses'], line=dict(color='green'),
                             mode='lines+markers', name='doses aplicadas', visible='legendonly'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['primeira_dose_dia'], marker_color='blue',
                         name='doses aplicadas<br>por dia (1ª dose)'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['segunda_dose_dia'], marker_color='green',
                         name='doses aplicadas<br>por dia (2ª dose)'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['terceira_dose_dia'], name='doses aplicadas<br>por dia (3ª dose)'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['quarta_dose_dia'], name='doses aplicadas<br>por dia (4ª dose)'))

    fig.add_trace(go.Bar(x=dados['data'], y=dados['dose_unica_dia'], name='doses aplicadas<br>por dia (dose única)'))

    fig.add_trace(go.Scatter(x=media_movel['data'], y=media_movel['aplicadas_dia'], line=dict(color='red'),
                             mode='lines+markers', name='média móvel de doses<br>aplicadas em 7 dias'))

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_1a_dose'], line=dict(color='orange'),
                             mode='lines+markers', name='população vacinada<br>1ª dose',
                             hovertemplate='%{y:.2f}%'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_2a_dose'], line=dict(color='goldenrod'),
                             mode='lines+markers', name='população vacinada<br>2ª dose',
                             hovertemplate='%{y:.2f}%', visible='legendonly'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_dose_unica'], mode='lines+markers',
                             name='população vacinada<br>dose única',
                             hovertemplate='%{y:.2f}%', visible='legendonly'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_3a_dose'], mode='lines+markers',
                             name='população vacinada<br>com a 3ª dose',
                             hovertemplate='%{y:.2f}%', visible='legendonly'),
                  secondary_y=True)

    fig.add_trace(go.Scatter(x=dados['data'], y=dados['perc_vacinadas_4a_dose'], mode='lines+markers',
                             name='população vacinada<br>com a 4ª dose',
                             hovertemplate='%{y:.2f}%', visible='legendonly'),
                  secondary_y=True)

    fig.update_layout(
        font=dict(family='Roboto'),
        title='Evolução da vacinação na cidade de São Paulo' +
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},  # para não truncar o nome de cada trace no hover
        template='plotly',
        barmode='stack',
        height=600
    )

    fig.update_yaxes(title_text='Doses aplicadas', secondary_y=False)
    fig.update_yaxes(title_text='População vacinada (%)', secondary_y=True)

    # fig.show()

    pio.write_html(fig, file='docs/graficos/vacinacao-cidade.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_traces(selector=dict(type='scatter'), mode='lines')

    fig.update_xaxes(nticks=10)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/vacinacao-cidade-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_populacao_vacinada(dados):
    filtro_data = dados.data == dados.data.max()
    filtro_estado = dados.municipio == 'ESTADO DE SAO PAULO'
    filtro_cidade = dados.municipio == 'SAO PAULO'

    dados_estado = dados.loc[filtro_data & filtro_estado].copy()
    dados_estado.loc[:, 'data'] = dados_estado.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    dados_cidade = dados.loc[filtro_data & filtro_cidade].copy()
    dados_cidade.loc[:, 'data'] = dados_cidade.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    fig = make_subplots(rows=1, cols=2, specs=[[{'type': 'domain'}, {'type': 'domain'}]])

    for i in range(1, 7):
        rotulos = [f'população com {i} dose(s)', f'população aguardando a {i}ª dose']

        pizza_estado = [dados_estado[f'{i}a_dose'].item(),
                        dados_estado['populacao'].item() - dados_estado[f'{i}a_dose'].item()]
        pizza_cidade = [dados_cidade[f'{i}a_dose'].item(),
                        dados_cidade['populacao'].item() - dados_cidade[f'{i}a_dose'].item()]

        fig.add_trace(go.Pie(labels=rotulos, values=pizza_estado, name=f'Estado_{i}a_dose',
                             marker=dict(colors=['green', 'red']), visible=True if i == 1 else False), 1, 1)
        fig.add_trace(go.Pie(labels=rotulos, values=pizza_cidade, name=f'Cidade_{i}a_dose',
                             marker=dict(colors=['green', 'red']), visible=True if i == 1 else False), 1, 2)

    fig.update_traces(hole=.4, hoverinfo="label+percent+name+value")

    titulo_a = 'População imunizada ('
    titulo_b = ') no estado e na cidade de São Paulo<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">'\
               'Governo do Estado de São Paulo</a></i>'

    opcao_dose1 = dict(label='1ª dose',
                        method='update',
                        args=[{'visible': [True, True, False, False, False, False, False, False, False, False, False, False]},
                              {'title.text': titulo_a + '1ª dose' + titulo_b},
                              {'showlegend': False}])

    opcao_dose2 = dict(label='2ª dose',
                       method='update',
                       args=[{'visible': [False, False, True, True, False, False, False, False, False, False, False, False]},
                             {'title.text': titulo_a + '2ª dose' + titulo_b},
                             {'showlegend': False}])

    opcao_dose3 = dict(label='3ª dose',
                       method='update',
                       args=[{'visible': [False, False, False, False, True, True, False, False, False, False, False, False]},
                             {'title.text': titulo_a + '3ª dose' + titulo_b},
                             {'showlegend': False}])

    opcao_dose4 = dict(label='4ª dose',
                       method='update',
                       args=[{'visible': [False, False, False, False, False, False, True, True, False, False, False, False]},
                             {'title.text': titulo_a + '4ª dose' + titulo_b},
                             {'showlegend': False}])

    opcao_dose5 = dict(label='5ª dose',
                       method='update',
                       args=[{'visible': [False, False, False, False, False, False, False, False, True, True, False, False]},
                             {'title.text': titulo_a + '5ª dose' + titulo_b},
                             {'showlegend': False}])

    opcao_dose6 = dict(label='6ª dose',
                       method='update',
                       args=[{'visible': [False, False, False, False, False, False, False, False, False, False, True, True]},
                             {'title.text': titulo_a + '6ª dose' + titulo_b},
                             {'showlegend': False}])

    fig.update_layout(
        title=titulo_a + '1ª dose' + titulo_b,
        font=dict(family='Roboto'),
        annotations=[dict(text='Estado de SP', x=0.17, y=0.5, font=dict(size=15, family='Roboto'), showarrow=False),
                     dict(text='Cidade de SP', x=0.80, y=0.5, font=dict(size=15, family='Roboto'), showarrow=False)],
        height=600,
        updatemenus=[go.layout.Updatemenu(active=0,
                                          buttons=[opcao_dose1, opcao_dose2, opcao_dose3,
                                                   opcao_dose4, opcao_dose5, opcao_dose6],
                                          x=0.001, xanchor='left',
                                          y=0.990, yanchor='top')],
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/populacao-vacinada.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        annotations=[dict(text='Estado', x=0.17, y=0.5, font=dict(size=9, family='Roboto'), showarrow=False),
                     dict(text='Cidade', x=0.85, y=0.5, font=dict(size=9, family='Roboto'), showarrow=False)],
        height=400,
        updatemenus=[go.layout.Updatemenu(active=0,
                                          buttons=[opcao_dose1, opcao_dose2, opcao_dose3,
                                                   opcao_dose4, opcao_dose5, opcao_dose6],
                                          x=0.001, xanchor='left',
                                          y=0.990, yanchor='top')],
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/populacao-vacinada-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_tipo_doses(dados):
    filtro_data = dados.data == dados.data.max()
    filtro_estado = dados.municipio == 'ESTADO DE SAO PAULO'
    filtro_cidade = dados.municipio == 'SAO PAULO'

    dados_estado = dados.loc[filtro_data & filtro_estado].copy()
    dados_estado.loc[:, 'data'] = dados_estado.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    dados_cidade = dados.loc[filtro_data & filtro_cidade].copy()
    dados_cidade.loc[:, 'data'] = dados_cidade.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    rotulos = ['1ª dose', '2ª dose', '3ª dose', '4ª dose', '5ª dose', '6ª dose', 'Dose única']
    pizza_estado = [dados_estado['1a_dose'].item(), dados_estado['2a_dose'].item(), dados_estado['3a_dose'].item(),
                    dados_estado['4a_dose'].item(), dados_estado['5a_dose'].item(), dados_estado['6a_dose'].item(),
                    dados_estado['dose_unica'].item()]
    pizza_cidade = [dados_cidade['1a_dose'].item(), dados_cidade['2a_dose'].item(), dados_cidade['3a_dose'].item(),
                    dados_cidade['4a_dose'].item(), dados_cidade['5a_dose'].item(), dados_cidade['6a_dose'].item(),
                    dados_cidade['dose_unica'].item()]

    fig = make_subplots(rows=1, cols=2, specs=[[{'type': 'domain'}, {'type': 'domain'}]])

    fig.add_trace(go.Pie(labels=rotulos, values=pizza_estado, name='Estado',
                         marker=dict(colors=['mediumturquoise', 'gold'])), 1, 1)
    fig.add_trace(go.Pie(labels=rotulos, values=pizza_cidade, name='Cidade',
                         marker=dict(colors=['mediumturquoise', 'gold'])), 1, 2)

    fig.update_traces(hole=.4, hoverinfo="label+percent+name+value")

    fig.update_layout(
        title='Tipos de doses aplicadas pelo estado e pela cidade de São Paulo'
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        font=dict(family='Roboto'),
        annotations=[dict(text='Estado de SP', x=0.17, y=0.5, font=dict(size=15, family='Roboto'), showarrow=False),
                     dict(text='Cidade de SP', x=0.80, y=0.5, font=dict(size=15, family='Roboto'), showarrow=False)],
        height=600
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/vacinas-tipo.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        annotations=[dict(text='Estado', x=0.17, y=0.5, font=dict(size=9, family='Roboto'), showarrow=False),
                     dict(text='Cidade', x=0.85, y=0.5, font=dict(size=9, family='Roboto'), showarrow=False)],
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/vacinas-tipo-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_doses_aplicadas(dados):
    filtro_data = dados.data == dados.data.max()
    filtro_estado = dados.municipio == 'ESTADO DE SAO PAULO'
    filtro_cidade = dados.municipio == 'SAO PAULO'

    dados_estado = dados.loc[filtro_data & filtro_estado].copy()
    dados_estado.loc[:, 'data'] = dados_estado.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    dados_cidade = dados.loc[filtro_data & filtro_cidade].copy()
    dados_cidade.loc[:, 'data'] = dados_cidade.data.apply(lambda dt: dt.strftime('%d/%b/%y'))

    rotulos = ['doses aplicadas', 'doses disponíveis para aplicação']
    pizza_estado = [dados_estado['total_doses'].item(), dados_estado['doses_recebidas'].item() - dados_estado['total_doses'].item()]
    pizza_cidade = [dados_cidade['total_doses'].item(), dados_cidade['doses_recebidas'].item() - dados_cidade['total_doses'].item()]

    fig = make_subplots(rows=1, cols=2, specs=[[{'type': 'domain'}, {'type': 'domain'}]])

    fig.add_trace(go.Pie(labels=rotulos, values=pizza_estado, name='Estado',
                         marker=dict(colors=['aquamarine', 'darkturquoise'])), 1, 1)
    fig.add_trace(go.Pie(labels=rotulos, values=pizza_cidade, name='Cidade',
                         marker=dict(colors=['aquamarine', 'darkturquoise'])), 1, 2)

    fig.update_traces(hole=.4, hoverinfo="label+percent+name+value")

    fig.update_layout(
        title='Vacinas disponíveis x aplicadas pelo estado e pela cidade de São Paulo'
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        font=dict(family='Roboto'),
        annotations=[dict(text='Estado de SP', x=0.17, y=0.5, font=dict(size=15, family='Roboto'), showarrow=False),
                     dict(text='Cidade de SP', x=0.80, y=0.5, font=dict(size=15, family='Roboto'), showarrow=False)],
        height=600
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/vacinas-aplicadas.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)

    # versão mobile
    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=10),
        annotations=[dict(text='Estado', x=0.17, y=0.5, font=dict(size=9, family='Roboto'), showarrow=False),
                     dict(text='Cidade', x=0.85, y=0.5, font=dict(size=9, family='Roboto'), showarrow=False)],
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/vacinas-aplicadas-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def gera_tabela_vacinacao(dados):
    data = datetime.strftime(dados.data.max(), format='%d/%m/%Y')
    dados_tab = dados.loc[dados.data == dados.data.max()].copy()
    dados_tab.columns = ['Data', 'Município', '1ª dose', '2ª dose', '3ª dose', '4ª dose', '5ª dose', '6ª dose',
                         'Dose única', 'Aplicadas no dia', 'Doses aplicadas', 'Doses recebidas', 'Aplicadas (%)',
                         '1ª dose (dia)', '1ª dose (%)', '2ª dose (dia)', '2ª dose (%)', '3ª dose (dia)',
                         '3ª dose (%)', '4ª dose (dia)', '4ª dose (%)', '5ª dose (dia)', '5ª dose (%)',
                         '6ª dose (dia)', '6ª dose (%)', 'Dose única (dia)', 'Dose única (%)',
                         '1ª dose ou Dose única (%)', 'Imunizados (%)', 'População']

    dados_tab.drop(columns='Aplicadas no dia', inplace=True)
    dados_tab.drop(columns='Imunizados (%)', inplace=True)
    dados_tab.fillna(0, inplace=True)
    dados_tab.sort_values(by='3ª dose (%)', ascending=False, inplace=True)

    dados_tab['Município'] = dados_tab['Município'].apply(lambda m: formata_municipio(m))
    dados_tab['1ª dose'] = dados_tab['1ª dose'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['1ª dose (%)'] = dados_tab['1ª dose (%)'].apply(lambda x: f'{x:8.2f}%'.replace('.', ','))
    dados_tab['2ª dose'] = dados_tab['2ª dose'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['2ª dose (%)'] = dados_tab['2ª dose (%)'].apply(lambda x: f'{x:8.2f}%'.replace('.', ','))
    dados_tab['3ª dose'] = dados_tab['3ª dose'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['3ª dose (%)'] = dados_tab['3ª dose (%)'].apply(lambda x: f'{x:8.2f}%'.replace('.', ','))
    dados_tab['4ª dose'] = dados_tab['4ª dose'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['4ª dose (%)'] = dados_tab['4ª dose (%)'].apply(lambda x: f'{x:8.2f}%'.replace('.', ','))
    dados_tab['5ª dose'] = dados_tab['5ª dose'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['5ª dose (%)'] = dados_tab['5ª dose (%)'].apply(lambda x: f'{x:8.2f}%'.replace('.', ','))
    dados_tab['6ª dose'] = dados_tab['6ª dose'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['6ª dose (%)'] = dados_tab['6ª dose (%)'].apply(lambda x: f'{x:8.2f}%'.replace('.', ','))
    dados_tab['Dose única'] = dados_tab['Dose única'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['Dose única (%)'] = dados_tab['Dose única (%)'].apply(lambda x: f'{x:8.2f}%'.replace('.', ','))
    dados_tab['Doses aplicadas'] = dados_tab['Doses aplicadas'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['1ª dose (dia)'] = dados_tab['1ª dose (dia)'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['2ª dose (dia)'] = dados_tab['2ª dose (dia)'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['3ª dose (dia)'] = dados_tab['3ª dose (dia)'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['4ª dose (dia)'] = dados_tab['4ª dose (dia)'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['5ª dose (dia)'] = dados_tab['5ª dose (dia)'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['6ª dose (dia)'] = dados_tab['6ª dose (dia)'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['Dose única (dia)'] = dados_tab['Dose única (dia)'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['Doses recebidas'] = dados_tab['Doses recebidas'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))
    dados_tab['Aplicadas (%)'] = dados_tab['Aplicadas (%)'].apply(lambda x: f'{x:8.2f}%'.replace('.', ','))
    dados_tab['População'] = dados_tab['População'].apply(lambda x: f'{x:8,.0f}'.replace(',', '.'))

    html_inicial = '''<!DOCTYPE html>
    <html lang="pt-br"> 
    <head> 
      <meta charset="utf-8"/> 
      <meta name="viewport" content="width=device-width, initial-scale=1"/> 
      <meta name="theme-color" content="#00AABB"/> 
      <meta name="description" content="Acompanhe os casos de Covid-19 na cidade e no estado de São Paulo"/> 
      <meta name="author" content="Davi Silva Rodrigues"/> 
      <title>Covid-19 em São Paulo</title> 
      <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap"/> 
      <link rel="stylesheet" href="https://cdn.datatables.net/1.10.25/css/jquery.dataTables.min.css"/> 
    </head> 
    <style>
      body {font-family: "Roboto", sans-serif;} 
      @media only screen and (max-width: 478px) {body {font-size: 3vw;}} 
      @media only screen and (min-width: 479px) {body {font-size: 2.25vw;}} 
      @media only screen and (min-width: 768px) {body {font-size: 1vw;}} 
    </style> 
    <body>Dados de ''' + data

    html_tabela = dados_tab.to_html(classes='display" id="tabela', index=False,
                                    columns=['Município', '1ª dose', '1ª dose (%)', '2ª dose', '2ª dose (%)',
                                             '3ª dose', '3ª dose (%)', '4ª dose', '4ª dose (%)', '5ª dose',
                                             '5ª dose (%)', '6ª dose', '6ª dose (%)', 'Dose única', 'Dose única (%)',
                                             'Doses aplicadas', '1ª dose (dia)', '2ª dose (dia)', '3ª dose (dia)',
                                             '4ª dose (dia)', '5ª dose (dia)', '6ª dose (dia)', 'Dose única (dia)',
                                             'Doses recebidas', 'Aplicadas (%)', 'População'])

    html_final = '''<script src="https://code.jquery.com/jquery-3.5.1.js"></script> 
    <script src="https://cdn.datatables.net/1.10.25/js/jquery.dataTables.min.js"></script> 
    <script> 
        $(document).ready(function() { 
            $("#tabela").DataTable({ 
                  scrollY:        "490px", 
                  scrollCollapse: true, 
                  paging:         false, 
                  order:          [[ 6, "desc" ]], 
                  language:       {decimal: ",",thousands: "."}, 
                  columnDefs:     [{targets: "_all",className: "dt-right"}] 
            });
        }); 
    </script>
    </body> 
    </html>'''

    with open('docs/graficos/tabela-vacinacao.html', 'w+', encoding='utf-8') as fo:
        fo.write(html_inicial + html_tabela + html_final)

    html_tabela = dados_tab.to_html(classes='display" id="tabela', index=False, columns=['Município', '3ª dose (%)'])
    html_final = html_final.replace('scrollY:        "490px"', 'scrollY:        "530px"')
    html_final = html_final.replace('order:          [[ 6, "desc" ]]', 'order:          [[ 1, "desc" ]]')

    with open('docs/graficos/tabela-vacinacao-mobile.html', 'w+', encoding='utf-8') as fo:
        fo.write(html_inicial + html_tabela + html_final)


def gera_distribuicao_imunizantes(dados_imunizantes):
    fig = go.Figure()

    for v in dados_imunizantes['vacina'].unique():
        fig.add_trace(go.Scatter(x=dados_imunizantes.loc[dados_imunizantes['vacina'] == v, 'data'].apply(lambda d: d.strftime('%d/%b/%y')),
                                 y=dados_imunizantes.loc[dados_imunizantes['vacina'] == v, 'aplicadas'],
                                 mode='lines', line=dict(width=0.5), stackgroup='one', name=v,
                                 text=dados_imunizantes.loc[dados_imunizantes['vacina'] == v, 'aplicadas'] \
                                                       .apply(lambda a: f'{a:,.0f}'.replace(',', '.') if a is not None else ''),
                                 hovertemplate='<br>Percentual: %{y:.2f}%<br>'
                                               'Doses aplicadas: %{text}<br>',
                                 groupnorm='percent'))

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)

    fig.update_layout(
        title='Distribuição de imunizantes no estado de São Paulo'
              '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
              'Governo do Estado de São Paulo</a></i>',
        font=dict(family='Roboto'),
        showlegend=True,
        xaxis_tickangle=45,
        hovermode='x unified',
        hoverlabel={'namelength': -1},
        template='plotly',
        xaxis_type='category',
        yaxis=dict(type='linear',
                   range=[1, 100],
                   ticksuffix='%'),
        height=600
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/imunizantes.html', include_plotlyjs='directory',
                   auto_open=False)

    # versão mobile
    fig.update_xaxes(nticks=10)

    fig.update_layout(
        showlegend=False,
        font=dict(size=11, family='Roboto'),
        margin=dict(l=1, r=1, b=1, t=90, pad=1),
        height=400
    )

    # fig.show()

    pio.write_html(fig, file='docs/graficos/imunizantes-mobile.html',
                   include_plotlyjs='directory', auto_open=False, auto_play=False)


def atualiza_service_worker(dados_estado):
    data_atual = dados_estado.data.iat[-1].strftime('%d/%m/%Y')

    with open('docs/serviceWorker.js', 'r') as file:
        filedata = file.read()

    versao_anterior = int(filedata[16:18])
    data_anterior = filedata[51:61]

    # primeira atualização no dia
    if filedata.count(data_atual) == 0:
        versao_atual = 1
        filedata = filedata.replace(data_anterior, data_atual)
    else:
        versao_atual = versao_anterior + 1

    print(f'\tCACHE_NAME: Covid19-SP-{data_atual}-{str(versao_atual).zfill(2)}')

    versao_anterior = "VERSAO = '" + str(versao_anterior).zfill(2) + "'"
    versao_atual = "VERSAO = '" + str(versao_atual).zfill(2) + "'"
    filedata = filedata.replace(versao_anterior, versao_atual)

    with open('docs/serviceWorker.js', 'w') as file:
        file.write(filedata)


if __name__ == '__main__':
    processa_doencas = False
    vacinacao = False

    if len(sys.argv) == 1:
        data_processamento = datetime.now()
        main()
    else:
        for i in range(int(sys.argv[1]), -1, -1):
            data_processamento = datetime.now() - timedelta(days=i)
            print(f'\nDia em processamento -> {data_processamento:%d/%m/%Y}\n')
            main()

