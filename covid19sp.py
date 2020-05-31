# -*- coding: utf-8 -*-
"""
Covid-19 em São Paulo

Gera gráficos para acompanhamento da pandemia de Covid-19
na cidade e no estado de São Paulo.

@author: https://github.com/DaviSRodrigues
"""

from datetime import datetime, timedelta
import locale
import numpy as np
import traceback

from bs4 import BeautifulSoup
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import requests
import tabula

def main():
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
    
    print('Carregando dados...')
    dados_cidade, hospitais_campanha, leitos_municipais = carrega_dados_cidade()
    dados_estado, isolamento, leitos_estaduais = carrega_dados_estado()
    
    print('\nPré-processando dados...')
    dados_cidade, hospitais_campanha, leitos_municipais, dados_estado, isolamento, leitos_estaduais = pre_processamento(dados_cidade, hospitais_campanha, leitos_municipais, dados_estado, isolamento, leitos_estaduais)
    efeito_cidade, efeito_estado = gera_dados_efeito_isolamento(dados_cidade, dados_estado, isolamento)
    
    print('\nGerando gráficos e tabelas...')    
    gera_graficos(dados_cidade, hospitais_campanha, leitos_municipais, dados_estado, isolamento, leitos_estaduais, efeito_cidade, efeito_estado)
    
    print('\nAtualizando serviceWorker.js...')    
    atualiza_service_worker(dados_cidade)
    
    print('\nFim')

def carrega_dados_cidade():
    dados_cidade = pd.read_csv('dados/dados_cidade_sp.csv', sep = ',')
    hospitais_campanha = pd.read_csv('dados/hospitais_campanha_sp.csv', sep = ',')
    leitos_municipais = pd.read_csv('dados/leitos_municipais.csv', sep = ',')
    
    return extrair_dados_prefeitura(dados_cidade, hospitais_campanha, leitos_municipais)

def extrair_dados_prefeitura(dados_cidade, hospitais_campanha, leitos_municipais):
    def formata_numero(valor):
        if '%' in valor:
            valor = valor.replace('%', '')
        
        if '.' in valor:
            return int(valor.replace('.', ''))
        
        return int(valor)
        
    try:
        #na máquina do GitHub, o horário é UTC
        #execuções até 9h BRT/12h UTC, buscarão dados do dia anterior
        data = datetime.now() - timedelta(hours = 12)
        data_str = data.strftime('%d/%m/%Y')
        
        if(dados_cidade.tail(1).data.iat[0] == data_str):
            dados_novos = False
            print('\tAtualizando dados existentes de ' + data_str + '...')
        else:
            dados_novos = True
            print('\tExtraindo dados novos de ' + data_str + '...')
        
        data_str = data.strftime('%d de %B de %Y').lower()
        
        #página de Boletins da Prefeitura de São Paulo
        URL = ('https://www.prefeitura.sp.gov.br/cidade/secretarias'
               '/saude/vigilancia_em_saude/doencas_e_agravos'
               '/coronavirus/index.php?p=295572')
        
        for i in range(2):
            pagina = requests.get(URL)

            soup = BeautifulSoup(pagina.text, 'html.parser')
            
            for link in soup.find_all('a'):
                if(data_str in link.text):
                    URL = link['href']
                    
        print('\tURL do boletim municipal: ' + URL)

        #com a URL do pdf correto, começa a extração de dados
        tabelas = tabula.read_pdf(URL, pages = 2, guess = False, lattice = True, 
                                  pandas_options = {'dtype': 'str'})
        resumo = tabelas[0]
        obitos = tabelas[1]

        tabelas = tabula.read_pdf(URL, pages = 3, guess = True, lattice = True, 
                                  pandas_options = {'dtype': 'str'})
        hm_camp = tabelas[0]
        info_leitos = tabelas[2]
        
        data_str = data.strftime('%d/%m/%Y')
        
        #atualiza dados municipais        
        if(dados_novos):
            novos_dados = {'data': data_str,
                           'suspeitos': [formata_numero(resumo.tail(1).iat[0,1])],
                           'confirmados': [formata_numero(resumo.tail(1).iat[0,2])],
                           'óbitos': [np.NaN],
                           'óbitos_suspeitos': [np.NaN]}
            
            dados_cidade = dados_cidade.append(
                pd.DataFrame(novos_dados,
                             columns = ['data', 'suspeitos', 'confirmados', 'óbitos', 'óbitos_suspeitos']),
                ignore_index = True)
        else:
            dados_cidade.loc[dados_cidade.data == data_str, 'suspeitos'] = formata_numero(resumo.tail(1).iat[0,1])
            dados_cidade.loc[dados_cidade.data == data_str, 'confirmados'] = formata_numero(resumo.tail(1).iat[0,2])
        
        #atualiza hospitais de campanha       
        if(dados_novos):
            novos_dados = {'data': [data_str, data_str],
                           'hospital': ['Pacaembu', 'Anhembi'],
                           'leitos': [200, 887],
                           'comum': [190, 823],
                           'uti': [10, 64],
                           'ocupação_comum': [formata_numero(hm_camp.iat[2, 2]), formata_numero(hm_camp.iat[2, 1])],
                           'ocupação_uti': [formata_numero(hm_camp.iat[3, 2]), formata_numero(hm_camp.iat[3, 1])],
                           'altas': [formata_numero(hm_camp.iat[4, 2]), formata_numero(hm_camp.iat[4, 1])],
                           'óbitos': [formata_numero(hm_camp.iat[5, 2]), formata_numero(hm_camp.iat[5, 1])],
                           'transferidos': [formata_numero(hm_camp.iat[6, 2]), formata_numero(hm_camp.iat[6, 1])],
                           'chegando': [formata_numero(hm_camp.iat[7, 2]), formata_numero(hm_camp.iat[7, 1])]}
            
            hospitais_campanha = hospitais_campanha.append(
                pd.DataFrame(novos_dados,
                             columns = ['data', 'hospital', 'leitos', 'comum', 'uti', 'ocupação_comum',
                                        'ocupação_uti', 'altas', 'óbitos', 'transferidos', 'chegando']),
                ignore_index = True)
        else:
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Pacaembu')), 'ocupação_comum'] = formata_numero(hm_camp.iat[2, 2])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Pacaembu')), 'ocupação_uti'] = formata_numero(hm_camp.iat[3, 2])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Pacaembu')), 'altas'] = formata_numero(hm_camp.iat[4, 2])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Pacaembu')), 'óbitos'] = formata_numero(hm_camp.iat[5, 2])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Pacaembu')), 'transferidos'] = formata_numero(hm_camp.iat[6, 2])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Pacaembu')), 'chegando'] = formata_numero(hm_camp.iat[7, 2])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Anhembi')), 'ocupação_comum'] = formata_numero(hm_camp.iat[2, 1])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Anhembi')), 'ocupação_uti'] = formata_numero(hm_camp.iat[3, 1])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Anhembi')), 'altas'] = formata_numero(hm_camp.iat[4, 1])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Anhembi')), 'óbitos'] = formata_numero(hm_camp.iat[5, 1])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Anhembi')), 'transferidos'] = formata_numero(hm_camp.iat[6, 1])
            hospitais_campanha.loc[((hospitais_campanha.data == data_str) & (hospitais_campanha.hospital == 'Anhembi')), 'chegando'] = formata_numero(hm_camp.iat[7, 1])
                
        #atualiza leitos municipais
        if(dados_novos):
            novos_dados = {'data': [data_str],
                           'pacientes_respiratorio': [formata_numero(info_leitos.iat[0, 1])],
                           'pacientes_suspeitos': [formata_numero(info_leitos.iat[1, 1])],
                           'internados_total': [formata_numero(info_leitos.iat[2, 1])],
                           'internados_uti': [formata_numero(info_leitos.iat[4, 1])],
                           'ventilação': [formata_numero(info_leitos.iat[5, 1])],
                           'ocupação_uti': [formata_numero(info_leitos.iat[6, 1])]}
            
            leitos_municipais = leitos_municipais.append(
                pd.DataFrame(novos_dados,
                             columns = ['data', 'pacientes_respiratorio', 'pacientes_suspeitos',
                                        'internados_total','internados_uti', 'ventilação', 'ocupação_uti']),
                ignore_index = True)
        else:
            leitos_municipais.loc[leitos_municipais.data == data_str, 'pacientes_respiratorio'] = formata_numero(info_leitos.iat[0, 1])
            leitos_municipais.loc[leitos_municipais.data == data_str, 'pacientes_suspeitos'] = formata_numero(info_leitos.iat[1, 1])
            leitos_municipais.loc[leitos_municipais.data == data_str, 'internados_total'] = formata_numero(info_leitos.iat[2, 1])
            leitos_municipais.loc[leitos_municipais.data == data_str, 'internados_uti'] = formata_numero(info_leitos.iat[4, 1])
            leitos_municipais.loc[leitos_municipais.data == data_str, 'ventilação'] = formata_numero(info_leitos.iat[5, 1])
            leitos_municipais.loc[leitos_municipais.data == data_str, 'ocupação_uti'] = formata_numero(info_leitos.iat[6, 1])
        
        #atualiza dados municipais do dia anterior
        data = datetime.now() - timedelta(hours = 12, days = 1)
        data_str = data.strftime('%d/%m/%Y')
        
        dados_cidade.loc[dados_cidade.data == data_str, 'óbitos'] = formata_numero(obitos.tail(1).iat[0,1])
        dados_cidade.loc[dados_cidade.data == data_str, 'óbitos_suspeitos'] = formata_numero(obitos.tail(1).iat[0,2])
        
        #após a extração dos dados e a montagem de dataframes, a atualização dos arquivos
        dados_cidade.to_csv('dados/dados_cidade_sp.csv', sep = ',', index  = False)
        hospitais_campanha.to_csv('dados/hospitais_campanha_sp.csv', sep = ',', index  = False)
        leitos_municipais.to_csv('dados/leitos_municipais.csv', sep = ',', index  = False)
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
    
    return dados_cidade, hospitais_campanha, leitos_municipais

def carrega_dados_estado():
    data = datetime.now() - timedelta(hours = 12)
    mes = data.strftime('%m')
    
    URL = ('https://www.seade.gov.br/wp-content/uploads/2020'
           '/' + mes + '/Dados-covid-19-estado.csv')

    try:
        print('\tAtualizando dados estaduais...')
        dados_estado = pd.read_table(URL, sep = ';', decimal = ',', encoding = 'latin-1')
        dados_estado.to_csv('dados/Dados-covid-19-estado.csv', sep = ';', decimal = ',', encoding = 'latin-1')
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        print('\tErro ao buscar *.csv da Seade: lendo arquivo local.')
        dados_estado = pd.read_csv('dados/Dados-covid-19-estado.csv', sep = ';', decimal = ',', encoding = 'latin-1')
    
    isolamento = pd.read_csv('dados/isolamento_social.csv', sep = ';')    
    leitos_estaduais = pd.read_csv('dados/leitos_estaduais.csv')
    
    return dados_estado, isolamento, leitos_estaduais

def pre_processamento(dados_cidade, hospitais_campanha, leitos_municipais, dados_estado, isolamento, leitos_estaduais):
    dados_cidade, hospitais_campanha, leitos_municipais = pre_processamento_cidade(dados_cidade, hospitais_campanha, leitos_municipais)
    dados_estado, isolamento, leitos_estaduais = pre_processamento_estado(dados_estado, isolamento, leitos_estaduais)
    
    return dados_cidade, hospitais_campanha, leitos_municipais, dados_estado, isolamento, leitos_estaduais

def pre_processamento_cidade(dados_cidade, hospitais_campanha, leitos_municipais):
    dados_cidade['data'] = pd.to_datetime(dados_cidade.data, format = '%d/%m/%Y')
    dados_cidade['dia'] = dados_cidade.data.apply(lambda d: d.strftime('%d %b'))
    
    hospitais_campanha['data'] = pd.to_datetime(hospitais_campanha.data, format = '%d/%m/%Y')
    hospitais_campanha['dia'] = hospitais_campanha.data.apply(lambda d: d.strftime('%d %b'))
        
    leitos_municipais['data'] = pd.to_datetime(leitos_municipais.data, format = '%d/%m/%Y')
    leitos_municipais['dia'] = leitos_municipais.data.apply(lambda d: d.strftime('%d %b'))
    
    def calcula_letalidade(series):
        #calcula a taxa de letalidade até a data atual
        series['letalidade'] = round((series['óbitos'] / series['confirmados']) * 100, 2)
        return series
    
    def calcula_dia(series):
        #localiza a linha atual passada como parâmetro e obtém a linha anterior
        indice = dados_cidade.index[dados_cidade.dia == series['dia']].item() - 1
        
        if(indice >= 0):
            casos_conf_anterior = dados_cidade.loc[indice, 'confirmados']
            casos_susp_anterior = dados_cidade.loc[indice, 'suspeitos']
            obitos_conf_anterior = dados_cidade.loc[indice, 'óbitos']
            obitos_susp_anterior = dados_cidade.loc[indice, 'óbitos_suspeitos']
            
            series['casos_dia'] = series['confirmados'] - casos_conf_anterior
            series['óbitos_dia'] = series['óbitos'] - obitos_conf_anterior
            series['casos_suspeitos_dia'] = series['suspeitos'] - casos_susp_anterior
            series['óbitos_suspeitos_dia'] = series['óbitos_suspeitos'] - obitos_susp_anterior
        
        return series
    
    dados_cidade = dados_cidade.apply(lambda linha: calcula_letalidade(linha), axis = 1)
    dados_cidade = dados_cidade.apply(lambda linha: calcula_dia(linha), axis = 1)
    
    return dados_cidade, hospitais_campanha, leitos_municipais

def pre_processamento_estado(dados_estado, isolamento, leitos_estaduais):
    #apaga as linhas completamente vazias
    dados_estado.dropna(how = 'all', inplace = True)
    #apaga as colunas completamente vazias
    dados_estado.dropna(how = 'all', axis = 1, inplace = True)
    dados_estado.columns = ['dia', 'total_casos', 'casos_dia', 'obitos_dia']
    dados_estado['data'] = pd.to_datetime(dados_estado.dia + ' 2020', format = '%d %b %Y')
    
    isolamento.columns = ['str_data', 'escala_cor', 'data', 'município', 'n_registros', 'uf', 'isolamento']
    #deixando apenas a primeira letra de cada palavra como maiúscula
    isolamento['município'] = isolamento.município.apply(lambda m: m.title())
    isolamento['isolamento'] = pd.to_numeric(isolamento.isolamento.str.replace('%', ''))
    isolamento['data'] = pd.to_datetime(isolamento.data, format = '%d/%m/%y')
    isolamento['dia'] = isolamento.data.apply(lambda d: d.strftime('%d %b'))
    isolamento.sort_values(by = ['data', 'isolamento'], inplace = True)
    
    leitos_estaduais['data'] = pd.to_datetime(leitos_estaduais.data, format = '%d/%m/%Y')
    leitos_estaduais['dia'] = leitos_estaduais.data.apply(lambda d: d.strftime('%d %b'))
    
    def calcula_letalidade(series):
        #localiza a linha atual passada como parâmetro e obtém a posição de acordo com o índice
        indice = dados_estado.index[dados_estado.dia == series['dia']].item()
        
        #calcula o total de óbitos (coluna 3) até a data atual
        series['total_obitos'] = dados_estado.loc[0:indice, 'obitos_dia'].sum()
        
        #calcula a taxa de letalidade até a data atual
        if series['total_casos'] > 0:
            series['letalidade'] = round((series['total_obitos'] / series['total_casos']) * 100, 2)
        
        return series
    
    dados_estado = dados_estado.apply(lambda linha: calcula_letalidade(linha), axis = 1)
    
    return dados_estado, isolamento, leitos_estaduais

def gera_dados_efeito_isolamento(dados_cidade, dados_estado, isolamento):
    #criar dataframe relação: comparar média de isolamento social de duas
    #semanas atrás com a quantidade de casos e de óbitos da semana atual
    def converte_semana(data):
        return data.strftime('%Y-W%U')
    
    def formata_semana_extenso(data):
        #http://portalsinan.saude.gov.br/calendario-epidemiologico-2020
        return datetime.strptime(data + '-0', '%Y-W%U-%w').strftime('%d/%b') + ' a ' + \
               datetime.strptime(data + '-6', '%Y-W%U-%w').strftime('%d/%b')
    
    isolamento['data_futuro'] = isolamento.data.apply(lambda d: d + timedelta(weeks = 2))
    
    filtro = isolamento.município == 'Estado De São Paulo'
    colunas = ['data_futuro', 'isolamento']

    esquerda = isolamento.loc[filtro, colunas] \
                         .groupby(['data_futuro']).mean().reset_index()

    esquerda.columns = ['data', 'isolamento']

    estado = dados_estado[['data', 'obitos_dia', 'casos_dia']] \
                    .groupby(['data']).sum().reset_index()
        
    estado.columns = ['data', 'obitos_semana', 'casos_semana']

    estado = esquerda.merge(estado, on = ['data'], how = 'outer', suffixes = ('_isolamento', '_estado'))

    estado['data'] = estado.data.apply(lambda d: converte_semana(d))

    estado = estado.groupby('data') \
                   .agg({'isolamento': 'mean', 'obitos_semana': sum, 'casos_semana': sum}) \
                   .reset_index()

    estado['data'] = estado.data.apply(lambda d: formata_semana_extenso(d))
    estado['isolamento'] = estado.isolamento.apply(lambda i: round(i, 2))

    efeito_estado = estado

    #dados municipais
    filtro = isolamento.município == 'São Paulo'
    colunas = ['data_futuro', 'isolamento']

    esquerda = isolamento.loc[filtro, colunas] \
                         .groupby(['data_futuro']).mean().reset_index()

    esquerda.columns = ['data', 'isolamento']

    cidade = dados_cidade[['data', 'óbitos_dia', 'casos_dia']] \
                    .groupby(['data']).sum().reset_index()

    cidade.columns = ['data', 'obitos_semana', 'casos_semana']
    cidade['município'] = 'São Paulo'

    cidade = esquerda.merge(cidade, on = ['data'], how = 'outer', suffixes = ('_isolamento', '_cidade'))

    cidade['data'] = cidade.data.apply(lambda d: converte_semana(d))
    
    cidade = cidade.groupby('data') \
                   .agg({'isolamento': 'mean', 'obitos_semana': sum, 'casos_semana': sum}) \
                   .reset_index()

    cidade['data'] = cidade.data.apply(lambda d: formata_semana_extenso(d))
    cidade['isolamento'] = cidade.isolamento.apply(lambda i: round(i, 2))

    efeito_cidade = cidade
    
    return efeito_cidade, efeito_estado

def gera_graficos(dados_cidade, hospitais_campanha, leitos_municipais, dados_estado, isolamento, leitos_estaduais, efeito_cidade, efeito_estado):
    gera_resumo_diario(dados_cidade, leitos_municipais, dados_estado, leitos_estaduais, isolamento)
    gera_casos_estado(dados_estado)
    gera_casos_cidade(dados_cidade)
    gera_isolamento_grafico(isolamento)
    gera_isolamento_tabela(isolamento)
    gera_efeito_estado(efeito_estado)
    gera_efeito_cidade(efeito_cidade)
    gera_leitos_estaduais(leitos_estaduais)
    gera_leitos_municipais(leitos_municipais)
    gera_hospitais_campanha(hospitais_campanha)

def gera_resumo_diario(dados_cidade, leitos_municipais, dados_estado, leitos_estaduais, isolamento):
    cabecalho = ['<b>Resumo diário</b>',
                 '<b>Estado de SP</b><br><i>' + dados_estado.tail(1).data.item().strftime('%d/%m/%Y') + '</i>', 
                 '<b>Cidade de SP</b><br><i>' + dados_cidade.tail(1).data.item().strftime('%d/%m/%Y') + '</i>']

    info = ['<b>Casos</b>', '<b>Casos no dia</b>', '<b>Óbitos</b>', '<b>Óbitos no dia</b>',
            '<b>Letalidade</b>', '<b>Ocupação de UTIs</b>', '<b>Isolamento</b>']
    
    filtro = (isolamento.município == 'Estado De São Paulo') & (isolamento.data == isolamento.data.max())
    indice = isolamento.loc[filtro, 'isolamento'].iloc[0]
    
    estado = ['{:4.0f}'.format(dados_estado.tail(1).total_casos.item()), #Casos
              '{:4.0f}'.format(dados_estado.tail(1).casos_dia.item()), #Casos por dia
              '{:4.0f}'.format(dados_estado.tail(1).total_obitos.item()), #Óbitos
              '{:4.0f}'.format(dados_estado.tail(1).obitos_dia.item()), #Óbitos por dia
              '{:02.2f}%'.format(dados_estado.tail(1).letalidade.item()), #Letalidade
              '{:02.1f}%'.format(leitos_estaduais.tail(1).sp_uti.item()), #Ocupação de UTI 
              '{:02.0f}%'.format(indice)] #Isolamento social
    
    filtro = (isolamento.município == 'São Paulo') & (isolamento.data == isolamento.data.max())
    indice = isolamento.loc[filtro, 'isolamento'].iloc[0]
    
    cidade = ['{:4.0f}'.format(dados_cidade.tail(1).confirmados.item()), #Casos
              '{:4.0f}'.format(dados_cidade.tail(1).casos_dia.item()), #Casos por dia
              '{:4.0f}'.format(dados_cidade.tail(2).head(1).óbitos.item()), #Óbitos
              '{:4.0f}'.format(dados_cidade.tail(2).head(1).óbitos_dia.item()), #Óbitos por dia
              '{:02.2f}%'.format(dados_cidade.tail(2).head(1).letalidade.item()), #Letalidade
              '{:02.0f}%'.format(leitos_municipais.tail(1).ocupação_uti.item()), #Ocupação de UTI 
              '{:02.0f}%'.format(indice)] #Isolamento social
    
    fig = go.Figure(data = [go.Table(header = dict(values = cabecalho,
                                                   fill_color = '#00aabb',
                                                   font = dict(color = 'white'),
                                                   align = ['right', 'right', 'right'],
                                                   line = dict(width = 5)),
                                     cells = dict(values = [info, estado, cidade],
                                                  fill_color = 'lavender',
                                                  align = 'right',
                                                  line = dict(width = 5)),
                                     columnwidth = [1, 1, 1])])
    
    fig.update_layout(
        font = dict(size = 15, family = 'Roboto'),
        margin = dict(l = 1, r = 1, b = 1, t = 30, pad = 5),
        annotations = [dict(x = 0, y = 0, showarrow = False, font = dict(size = 13),
                            text = '<i><b>Fontes:</b> <a href = "https://www.seade.gov.br/coronavirus/">Governo do Estado ' + 
                                   'de São Paulo</a> e <a href = "https://www.prefeitura.sp.gov.br/cidade/secretarias/' +
                                   'saude/vigilancia_em_saude/doencas_e_agravos/coronavirus/index.php?p=295572">Prefeitura' +
                                   ' de São Paulo</a></i>')],
        height = 350
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/resumo.html', include_plotlyjs = 'directory', auto_open = False)
    
    fig.update_layout(
        font = dict(size = 13),
        margin = dict(l = 1, r = 1, b = 1, t = 30, pad = 5),
        annotations = [dict(x = 0, y = 0)],
        height = 340
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/resumo-mobile.html', include_plotlyjs = 'directory', auto_open = False)

def gera_casos_estado(dados):
    fig = make_subplots(specs = [[{"secondary_y": True}]])
    
    fig.add_trace(go.Scatter(x = dados['dia'], y = dados['total_casos'], line = dict(color = 'blue'),
                             mode = 'lines+markers', name = 'casos confirmados'))
    
    fig.add_trace(go.Bar(x = dados['dia'], y = dados['casos_dia'], marker_color = 'blue',
                         name = 'casos por dia'))
    
    fig.add_trace(go.Scatter(x = dados['dia'], y = dados['total_obitos'], line = dict(color = 'red'),
                             mode = 'lines+markers', name = 'total de óbitos'))
    
    fig.add_trace(go.Bar(x = dados['dia'], y = dados['obitos_dia'], marker_color = 'red',
                         name = 'óbitos por dia', visible = 'legendonly'))
    
    fig.add_trace(go.Scatter(x = dados['dia'], y = dados['letalidade'], line = dict(color = 'green'),
                             mode = 'lines+markers', name = 'letalidade', hovertemplate = '%{y:.2f}%'),
                  secondary_y = True)
    
    d = dados.dia.size
    
    frames = [dict(data = [dict(type = 'scatter', x = dados.dia[:d+1], y = dados.total_casos[:d+1]),
                           dict(type = 'bar', x = dados.dia[:d+1], y = dados.casos_dia[:d+1]),
                           dict(type = 'scatter', x = dados.dia[:d+1], y = dados.total_obitos[:d+1]),
                           dict(type = 'bar', x = dados.dia[:d+1], y = dados.obitos_dia[:d+1]),
                           dict(type = 'scatter', x = dados.dia[:d+1], y = dados.letalidade[:d+1])],
                   traces = [0, 1, 2, 3, 4],
                  ) for d in range(0, d)]
    
    fig.frames = frames
    
    botoes = [dict(label = 'Animar', method = 'animate',
                   args = [None,dict(frame = dict(duration = 200, redraw = True), fromcurrent = True, mode = 'immediate')])]
    
    fig.update_layout(
        font = dict(family = 'Roboto'),
        title = 'Casos confirmados de Covid-19 no Estado de São Paulo' +
                '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
                'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle = 45,
        hovermode = 'x unified',
        hoverlabel = {'namelength' : -1}, #para não truncar o nome de cada trace no hover
        template = 'plotly',
        updatemenus = [dict(type = 'buttons', showactive = False,
                            x = 0.05, y = 0.95,
                            xanchor = 'left', yanchor = 'top',
                            pad = dict(t = 0, r = 10), buttons = botoes)]
    )
    
    fig.update_yaxes(title_text = 'Número de casos ou óbitos', secondary_y = False)
    fig.update_yaxes(title_text = 'Taxa de letalidade (%)', secondary_y = True)
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/casos-estado.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
    #versão mobile
    fig.update_traces(selector = dict(type = 'scatter'), mode = 'lines')
    
    fig.update_xaxes(nticks = 10)
    
    fig.update_layout(
        showlegend = False,
        font = dict(size = 11),
        margin = dict(l = 1, r = 1, b = 1, t = 90, pad = 10)
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/casos-estado-mobile.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
def gera_casos_cidade(dados):
    fig = make_subplots(specs = [[{"secondary_y": True}]])
    
    fig.add_trace(go.Scatter(x = dados['dia'], y = dados['suspeitos'], line = dict(color = 'teal'),
                             mode = 'lines+markers', name = 'casos suspeitos', visible = 'legendonly'))
    
    fig.add_trace(go.Bar(x = dados['dia'], y = dados['casos_suspeitos_dia'], marker_color = 'teal',
                         name = 'casos suspeitos por dia', visible = 'legendonly'))
    
    fig.add_trace(go.Scatter(x = dados['dia'], y = dados['confirmados'], line = dict(color = 'blue'),
                             mode = 'lines+markers', name = 'casos confirmados'))
    
    fig.add_trace(go.Bar(x = dados['dia'], y = dados['casos_dia'], marker_color = 'blue',
                         name = 'casos confirmados por dia'))
    
    fig.add_trace(go.Scatter(x = dados['dia'], y = dados['óbitos_suspeitos'], line = dict(color = 'orange'),
                             mode = 'lines+markers', name = 'óbitos suspeitos', visible = 'legendonly'))
    
    fig.add_trace(go.Bar(x = dados['dia'], y = dados['óbitos_suspeitos_dia'], marker_color = 'orange',
                         name = 'óbitos suspeitos por dia', visible = 'legendonly'))
    
    fig.add_trace(go.Scatter(x = dados['dia'], y = dados['óbitos'], line = dict(color = 'red'),
                             mode = 'lines+markers', name = 'óbitos confirmados'))
    
    fig.add_trace(go.Bar(x = dados['dia'], y = dados['óbitos_dia'], marker_color = 'red',
                             name = 'óbitos confirmados por dia', visible = 'legendonly'))
    
    fig.add_trace(go.Scatter(x = dados['dia'], y = dados['letalidade'], line = dict(color = 'green'),
                             mode = 'lines+markers', name = 'letalidade', hovertemplate = '%{y:.2f}%'),
                  secondary_y = True)
    
    d = dados.dia.size
    
    frames = [dict(data = [dict(type = 'scatter', x = dados.dia[:d+1], y = dados.suspeitos[:d+1]),
                           dict(type = 'bar', x = dados.dia[:d+1], y = dados.casos_suspeitos_dia[:d+1]),
                           dict(type = 'scatter', x = dados.dia[:d+1], y = dados.confirmados[:d+1]),
                           dict(type = 'bar', x = dados.dia[:d+1], y = dados.casos_dia[:d+1]),
                           dict(type = 'scatter', x = dados.dia[:d+1], y = dados.óbitos_suspeitos[:d+1]),
                           dict(type = 'bar', x = dados.dia[:d+1], y = dados.óbitos_suspeitos_dia[:d+1]),
                           dict(type = 'scatter', x = dados.dia[:d+1], y = dados.óbitos[:d+1]),
                           dict(type = 'bar', x = dados.dia[:d+1], y = dados.óbitos_dia[:d+1]),
                           dict(type = 'scatter', x = dados.dia[:d+1], y = dados.letalidade[:d+1])],
                   traces = [0, 1, 2, 3, 4, 5, 6, 7, 8],
                  ) for d in range(0, d)]
    
    fig.frames = frames
    
    botoes = [dict(label = 'Animar', method = 'animate',
                   args = [None,dict(frame = dict(duration = 200, redraw = True), fromcurrent = True, mode = 'immediate')])]
    
    fig.update_layout(
        font = dict(family = 'Roboto'),
        title = 'Casos confirmados de Covid-19 na cidade de São Paulo' +
                '<br><i>Fonte: <a href = "https://www.prefeitura.sp.gov.br/cidade/' +
                'secretarias/saude/vigilancia_em_saude/doencas_e_agravos/coronavirus/' +
                'index.php?p=295572">Prefeitura de São Paulo</a></i>',
        xaxis_tickangle = 45,
        hovermode = 'x unified',
        hoverlabel = {'namelength' : -1}, #para não truncar o nome de cada trace no hover
        template = 'plotly',
        updatemenus = [dict(type = 'buttons', showactive = False,
                            x = 0.05, y = 0.95,
                            xanchor = 'left', yanchor = 'top',
                            pad = dict(t = 0, r = 10), buttons = botoes)]
    )
    
    fig.update_yaxes(title_text = 'Número de casos ou óbitos', secondary_y = False)
    fig.update_yaxes(title_text = 'Taxa de letalidade (%)', secondary_y = True)
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/casos-cidade.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
    #versão mobile
    fig.update_traces(selector = dict(type = 'scatter'), mode = 'lines')
    
    fig.update_xaxes(nticks = 10)
    
    fig.update_layout(
        showlegend = False,
        font = dict(size = 11),
        margin = dict(l = 1, r = 1, b = 1, t = 90, pad = 20)
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/casos-cidade-mobile.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)

def gera_isolamento_grafico(isolamento):
    fig = go.Figure()

    #lista de municípios em ordem de maior índice de isolamento
    l_municipios = list(isolamento.sort_values(by = ['data', 'isolamento', 'município'], ascending = False).município.unique())
    
    #series em vez de list, para que seja possível utilizar o método isin
    s_municipios = pd.Series(l_municipios)
    
    titulo_a = 'Índice de adesão ao isolamento social - '
    titulo_b = '<br><i>Fonte: <a href = "https://www.saopaulo.sp.gov.br/coronavirus/isolamento/">Governo do Estado de São Paulo</a></i>'
    
    cidades_iniciais = ['Estado De São Paulo', 'São Paulo', 'Guarulhos', 'Osasco', 'Jundiaí', 'Caieiras', 
                        'Campinas', 'Santo André', 'Mauá', 'Francisco Morato', 'Poá']
    
    for m in l_municipios:
        grafico = isolamento[isolamento.município == m]
        
        if m in cidades_iniciais:
            fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['isolamento'], name = m,
                                     mode = 'lines+markers', hovertemplate = '%{y:.0f}%', visible = True))
        else:
            fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['isolamento'], name = m,
                                     mode = 'lines+markers+text', textposition = 'top center', 
                                     text = grafico['isolamento'].apply(lambda i: str(i) + '%'), hovertemplate = '%{y:.0f}%', visible = False))
            
    opcao_metro = dict(label = 'Região Metropolitana',
                        method = 'update',
                        args = [{'visible': s_municipios.isin(cidades_iniciais)},
                                {'title.text': titulo_a + 'Região Metropolitana' + titulo_b},
                                {'showlegend': True}])
    
    opcao_estado = dict(label = 'Estado de São Paulo',
                        method = 'update',
                        args = [{'visible': s_municipios.isin(['Estado De São Paulo'])},
                                {'title.text': titulo_a + 'Estado de São Paulo' + titulo_b},
                                {'showlegend': False}])
    
    def cria_lista_opcoes(cidade):
        return dict(label = cidade,
                    method = 'update',
                    args = [{'visible': s_municipios.isin([cidade])},
                            {'title.text': titulo_a + cidade + titulo_b},
                            {'showlegend': False}])
        
    fig.update_layout(
        font = dict(family = 'Roboto'),
        title = titulo_a + 'Região Metropolitana' + titulo_b,
        xaxis_tickangle = 45,
        yaxis_title = 'Índice de isolamento social (%)',
        hovermode = 'x unified',
        hoverlabel = {'namelength' : -1}, #para não truncar o nome de cada trace no hover
        template = 'plotly',
        updatemenus = [go.layout.Updatemenu(active = 0,
                buttons = [opcao_metro, opcao_estado] + list(s_municipios.apply(lambda m: cria_lista_opcoes(m))),
                x = 0.001, xanchor = 'left',
                y = 0.990, yanchor = 'top'
                )]
    )
        
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/isolamento.html', include_plotlyjs = 'directory', auto_open = False)
    
    #versão mobile
    fig.update_traces(mode = 'lines+text')
    
    fig.update_xaxes(nticks = 10)
        
    fig.update_layout(
        showlegend = False,
        font = dict(size = 11),
        margin = dict(l = 1, r = 1, b = 1, t = 90, pad = 10)
    )
        
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/isolamento-mobile.html', include_plotlyjs = 'directory', auto_open = False)

def gera_isolamento_tabela(isolamento):
    dados = isolamento.loc[isolamento.data == isolamento.data.max(), ['data', 'município', 'isolamento']]
    dados.sort_values(by = ['isolamento', 'município'], ascending = False, inplace = True)
    
    cabecalho = ['<b>Cidade</b>', 
                 '<b>Isolamento</b><br><i>' + dados.data.iloc[0].strftime('%d/%m/%Y') + '</i>']
    
    fig = go.Figure(data = [go.Table(header = dict(values = cabecalho,
                                                   fill_color = '#00aabb',
                                                   font = dict(color = 'white'),
                                                   align = 'right',
                                                   line = dict(width = 5)),
                                     cells = dict(values = [dados.município, dados.isolamento.map('{:02.0f}%'.format)],
                                                  fill_color = 'lavender',
                                                  align = 'right',
                                                  line = dict(width = 5),
                                                  height = 30),
                                     columnwidth = [1, 1])])
    
    fig.update_layout(
        font = dict(size = 15, family = 'Roboto'),
        margin = dict(l = 1, r = 1, b = 1, t = 30, pad = 5),
        annotations = [dict(x = 0, y = 0, showarrow = False, font = dict(size = 13),
                            text = '<i><b>Fonte:</b> <a href = "https://www.saopaulo.sp.gov.br/coronavirus/isolamento/">'
                                   'Governo do Estado de São Paulo</a></i>')]
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/tabela-isolamento.html', include_plotlyjs = 'directory', auto_open = False)
    
    fig.update_layout(
        font = dict(size = 13),
        margin = dict(l = 1, r = 1, b = 1, t = 30, pad = 5),
        annotations = [dict(x = 0, y = 0)]
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/tabela-isolamento-mobile.html', include_plotlyjs = 'directory', auto_open = False)

def gera_efeito_estado(efeito_estado):
    fig = make_subplots(specs = [[{"secondary_y": True}]])

    grafico = efeito_estado
    
    fig.add_trace(go.Scatter(x = grafico['data'], y = grafico['isolamento'], line = dict(color = 'orange'),
                             name = 'isolamento médio<br>de 2 semanas atrás',
                             hovertemplate = '%{y:.2f}%'), secondary_y = True)
    
    fig.add_trace(go.Bar(x = grafico['data'], y = grafico['casos_semana'], marker_color = 'blue',
                         name = 'casos na<br>semana atual'))
    
    fig.add_trace(go.Bar(x = grafico['data'], y = grafico['obitos_semana'], marker_color = 'red',
                         name = 'óbitos na<br>semana atual'))
    
    d = grafico.data.size
    
    frames = [dict(data = [dict(type = 'scatter', x = grafico.data[:d+1], y = grafico.isolamento[:d+1]),
                           dict(type = 'bar', x = grafico.data[:d+1], y = grafico.casos_semana[:d+1]),
                           dict(type = 'bar', x = grafico.data[:d+1], y = grafico.obitos_semana[:d+1])],
                   traces = [0, 1, 2],
                  ) for d in range(0, d)]
    
    fig.frames = frames
    
    botoes = [dict(label = 'Animar', method = 'animate',
                   args = [None,dict(frame = dict(duration = 400, redraw = True), fromcurrent = True, mode = 'immediate')])]
    
    fig.update_yaxes(title_text = 'Número de casos ou óbitos', secondary_y = False)
    fig.update_yaxes(title_text = 'Taxa média de isolamento há 2 semanas (%)', secondary_y = True)
    
    fig.update_layout(
        font = dict(family = 'Roboto'),
        title = 'Efeito do isolamento social no Estado de São Paulo' +
                '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
                'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle = 30,
        hovermode = 'x unified',
        hoverlabel = {'namelength' : -1},
        template = 'plotly',
        updatemenus = [dict(type = 'buttons', showactive = False,
                            x = 0.05, y = 0.95,
                            xanchor = 'left', yanchor = 'top',
                            pad = dict(t = 0, r = 10), buttons = botoes)]
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/efeito-estado.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
    #versão mobile
    fig.update_traces(selector = dict(type = 'scatter'), mode = 'lines')
    
    fig.update_xaxes(nticks = 10)
        
    fig.update_layout(
        showlegend = False,
        font = dict(size = 11),
        margin = dict(l = 1, r = 1, b = 1, t = 90, pad = 10)
    )
        
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/efeito-estado-mobile.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
def gera_efeito_cidade(efeito_cidade):
    fig = make_subplots(specs = [[{"secondary_y": True}]])
    
    grafico = efeito_cidade
    
    fig.add_trace(go.Scatter(x = grafico['data'], y = grafico['isolamento'], line = dict(color = 'orange'),
                             name = 'isolamento médio<br>de 2 semanas atrás',
                             hovertemplate = '%{y:.2f}%'), secondary_y = True)
    
    fig.add_trace(go.Bar(x = grafico['data'], y = grafico['casos_semana'], marker_color = 'blue',
                         name = 'casos na<br>semana atual'))
    
    fig.add_trace(go.Bar(x = grafico['data'], y = grafico['obitos_semana'], marker_color = 'red',
                         name = 'óbitos na<br>semana atual'))
    
    d = grafico.data.size
    
    frames = [dict(data = [dict(type = 'scatter', x = grafico.data[:d+1], y = grafico.isolamento[:d+1]),
                           dict(type = 'bar', x = grafico.data[:d+1], y = grafico.casos_semana[:d+1]),
                           dict(type = 'bar', x = grafico.data[:d+1], y = grafico.obitos_semana[:d+1])],
                   traces = [0, 1, 2],
                  ) for d in range(0, d)]
    
    fig.frames = frames
    
    botoes = [dict(label = 'Animar', method = 'animate',
                   args = [None,dict(frame = dict(duration = 400, redraw = True), fromcurrent = True, mode = 'immediate')])]
    
    fig.update_yaxes(title_text = 'Número de casos ou óbitos', secondary_y = False)
    fig.update_yaxes(title_text = 'Taxa média de isolamento há 2 semanas (%)', secondary_y = True)
    
    fig.update_layout(
        font = dict(family = 'Roboto'),
        title = 'Efeito do isolamento social na Cidade de São Paulo' +
                '<br><i>Fonte: <a href = "https://www.prefeitura.sp.gov.br/cidade/' +
                'secretarias/saude/vigilancia_em_saude/doencas_e_agravos/coronavirus/' +
                'index.php?p=295572">Prefeitura de São Paulo</a></i>',
        xaxis_tickangle = 30,
        hovermode = 'x unified',
        hoverlabel = {'namelength' : -1},
        template = 'plotly',
        updatemenus = [dict(type = 'buttons', showactive = False,
                            x = 0.05, y = 0.95,
                            xanchor = 'left', yanchor = 'top',
                            pad = dict(t = 0, r = 10), buttons = botoes)]
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/efeito-cidade.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
    #versão mobile
    fig.update_traces(selector = dict(type = 'scatter'), mode = 'lines')
    
    fig.update_xaxes(nticks = 10)
        
    fig.update_layout(
        showlegend = False,
        font = dict(size = 11),
        margin = dict(l = 1, r = 1, b = 1, t = 90, pad = 10)
    )
        
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/efeito-cidade-mobile.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
def gera_leitos_estaduais(leitos):
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['rmsp_uti'],
                             mode = 'lines+markers', name = 'UTI<br>(região metropolitana)', 
                             hovertemplate = '%{y:.1f}%'))
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['rmsp_enfermaria'],
                             mode = 'lines+markers', name = 'enfermaria<br>(região metropolitana)', 
                             hovertemplate = '%{y:.1f}%'))
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['sp_uti'],
                             mode = 'lines+markers', name = 'UTI<br>(estado)', hovertemplate = '%{y:.1f}%'))
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['sp_enfermaria'],
                             mode = 'lines+markers', name = 'enfermaria<br>(estado)', hovertemplate = '%{y:.1f}%'))
    
    d = leitos.dia.size
    
    frames = [dict(data = [dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.rmsp_uti[:d+1]),
                           dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.rmsp_enfermaria[:d+1]),
                           dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.sp_uti[:d+1]),
                           dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.sp_enfermaria[:d+1])],
                   traces = [0, 1, 2, 3],
                  ) for d in range(0, d)]
    
    fig.frames = frames
    
    botoes = [dict(label = 'Animar', method = 'animate',
                   args = [None,dict(frame = dict(duration = 200, redraw = True), fromcurrent = True, mode = 'immediate')])]
    
    fig.update_layout(
        font = dict(family = 'Roboto'),
        title = 'Ocupação de leitos Covid-19 no Estado de São Paulo' +
                '<br><i>Fonte: <a href = "https://www.seade.gov.br/coronavirus/">' +
                'Governo do Estado de São Paulo</a></i>',
        xaxis_tickangle = 45,
        yaxis_title = 'Taxa de ocupação dos leitos (%)',
        hovermode = 'x unified',
        hoverlabel = {'namelength' : -1}, #para não truncar o nome de cada trace no hover
        template = 'plotly',
        updatemenus = [dict(type = 'buttons', showactive = False,
                            x = 0.05, y = 0.95,
                            xanchor = 'left', yanchor = 'top',
                            pad = dict(t = 0, r = 10), buttons = botoes)]
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/leitos-estaduais.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
    #versão mobile
    fig.update_traces(mode = 'lines')
    
    fig.update_xaxes(nticks = 10)
    
    fig.update_layout(
        showlegend = False,
        font = dict(size = 11),
        margin = dict(l = 1, r = 1, b = 1, t = 90, pad = 10)
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/leitos-estaduais-mobile.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
def gera_leitos_municipais(leitos):
    fig = make_subplots(specs = [[{"secondary_y": True}]])
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['ocupação_uti'],
                             mode = 'lines+markers', name = 'taxa de ocupação de UTI',
                             hovertemplate = '%{y:.0f}%'),
                  secondary_y = True)
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['internados_uti'],
                             mode = 'lines+markers', name = 'pacientes internados em UTI'))
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['ventilação'],
                             mode = 'lines+markers', name = 'pacientes internados em<br>ventilação mecânica'))
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['internados_total'], visible = 'legendonly',
                             mode = 'lines+markers', name = 'total de pacientes internados'))
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['pacientes_respiratorio'], visible = 'legendonly',
                             mode = 'lines+markers', name = 'pacientes atendidos com<br>quadro respiratório'))
    
    fig.add_trace(go.Scatter(x = leitos['dia'], y = leitos['pacientes_suspeitos'], visible = 'legendonly',
                             mode = 'lines+markers', name = 'pacientes atendidos com<br>suspeita de Covid-19'))
    
    d = leitos.dia.size
    
    frames = [dict(data = [dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.ocupação_uti[:d+1]),
                           dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.internados_uti[:d+1]),
                           dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.ventilação[:d+1]),
                           dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.internados_total[:d+1]),
                           dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.pacientes_respiratorio[:d+1]),
                           dict(type = 'scatter', x = leitos.dia[:d+1], y = leitos.pacientes_suspeitos[:d+1])],
                   traces = [0, 1, 2, 3, 4, 5],
                  ) for d in range(0, d)]
    
    fig.frames = frames
    
    botoes = [dict(label = 'Animar', method = 'animate',
                   args = [None,dict(frame = dict(duration = 200, redraw = True), fromcurrent = True, mode = 'immediate')])]
    
    fig.update_layout(
        font = dict(family = 'Roboto'),
        title = 'Situação da Rede Hospitalar Municipal' + 
                '<br><i>Fonte: <a href = "https://www.prefeitura.sp.gov.br/cidade/' +
                'secretarias/saude/vigilancia_em_saude/doencas_e_agravos/coronavirus/' +
                'index.php?p=295572">Prefeitura de São Paulo</a></i>',
        xaxis_tickangle = 45,
        hovermode = 'x unified',
        hoverlabel = {'namelength' : -1}, #para não truncar o nome de cada trace no hover
        template = 'plotly',
        showlegend = True,
        updatemenus = [dict(type = 'buttons', showactive = False,
                            x = 0.05, y = 0.95,
                            xanchor = 'left', yanchor = 'top',
                            pad = dict(t = 0, r = 10), buttons = botoes)]
    )
    
    fig.update_yaxes(title_text = 'Número de pacientes', secondary_y = False)
    fig.update_yaxes(title_text = 'Taxa de ocupação de UTI (%)', secondary_y = True)
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/leitos-municipais.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
    #versão mobile
    fig.update_traces(mode = 'lines')
    
    fig.update_xaxes(nticks = 10)
    
    fig.update_layout(
        font = dict(size = 11),
        margin = dict(l = 1, r = 1, b = 1, t = 90, pad = 20),
        showlegend = False
    )
    
    # fig.show()
    
    pio.write_html(fig, file = 'docs/graficos/leitos-municipais-mobile.html',
                   include_plotlyjs = 'directory', auto_open = False, auto_play = False)
    
def gera_hospitais_campanha(hospitais_campanha):
    for h in hospitais_campanha.hospital.unique():
        grafico = hospitais_campanha[hospitais_campanha.hospital == h]
        
        fig = go.Figure()
    
        fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['comum'],
                                 mode = 'lines+markers', name = 'leitos de enfermaria'))
    
        fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['ocupação_comum'],
                                 mode = 'lines+markers', name = 'internados em leitos<br>de enfermaria'))
    
        fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['uti'],
                                 mode = 'lines+markers', name = 'leitos de estabilização'))
    
        fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['ocupação_uti'],
                                 mode = 'lines+markers', name = 'internados em leitos<br>de estabilização'))
        
        fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['altas'],
                             mode = 'lines+markers', name = 'altas', visible = 'legendonly'))
        
        fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['óbitos'],
                             mode = 'lines+markers', name = 'óbitos', visible = 'legendonly'))
        
        fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['transferidos'],
                             mode = 'lines+markers', name = 'transferidos para Hospitais<br>após agravamento clínico',
                             visible = 'legendonly'))
        
        fig.add_trace(go.Scatter(x = grafico['dia'], y = grafico['chegando'],
                             mode = 'lines+markers', name = 'pacientes em processo de<br>transferência para internação<br>no HMCamp', 
                             visible = 'legendonly'))
        
        d = grafico.dia.size
    
        frames = [dict(data = [dict(type = 'scatter', x = grafico.dia[:d+1], y = grafico.comum[:d+1]),
                               dict(type = 'scatter', x = grafico.dia[:d+1], y = grafico.ocupação_comum[:d+1]),
                               dict(type = 'scatter', x = grafico.dia[:d+1], y = grafico.uti[:d+1]),
                               dict(type = 'scatter', x = grafico.dia[:d+1], y = grafico.ocupação_uti[:d+1]),
                               dict(type = 'scatter', x = grafico.dia[:d+1], y = grafico.altas[:d+1]),
                               dict(type = 'scatter', x = grafico.dia[:d+1], y = grafico.óbitos[:d+1]),
                               dict(type = 'scatter', x = grafico.dia[:d+1], y = grafico.transferidos[:d+1]),
                               dict(type = 'scatter', x = grafico.dia[:d+1], y = grafico.chegando[:d+1])],
                       traces = [0, 1, 2, 3, 4, 5, 6, 7],
                      ) for d in range(0, d)]
    
        fig.frames = frames
    
        botoes = [dict(label = 'Animar', method = 'animate',
                       args = [None,dict(frame = dict(duration = 200, redraw = True), fromcurrent = True, mode = 'immediate')])]
    
        fig.update_layout(
            font = dict(family = 'Roboto'),
            title = 'Ocupação dos leitos do HMCamp ' + h + 
                    '<br><i>Fonte: <a href = "https://www.prefeitura.sp.gov.br/cidade/' +
                    'secretarias/saude/vigilancia_em_saude/doencas_e_agravos/coronavirus/' +
                    'index.php?p=295572">Prefeitura de São Paulo</a></i>',
            xaxis_tickangle = 45,
            yaxis_title = 'Número de leitos ou pacientes',
            hovermode = 'x unified',
            hoverlabel = {'namelength' : -1}, #para não truncar o nome de cada trace no hover
            template = 'plotly',
            updatemenus = [dict(type = 'buttons', showactive = False,
                            x = 0.05, y = 0.95,
                            xanchor = 'left', yanchor = 'top',
                            pad = dict(t = 0, r = 10), buttons = botoes)]
        )
    
        # fig.show()
        
        pio.write_html(fig, file = 'docs/graficos/' + h.lower() + '.html',
                       include_plotlyjs = 'directory', auto_open = False, auto_play = False)
        
        #versão mobile
        fig.update_traces(mode = 'lines')
    
        fig.update_xaxes(nticks = 10)
        
        fig.update_layout(
            showlegend = False,
            font = dict(size = 11),
            margin = dict(l = 1, r = 1, b = 1, t = 90, pad = 20)
        )
    
        # fig.show()
        
        pio.write_html(fig, file = 'docs/graficos/' + h.lower() + '-mobile.html',
                       include_plotlyjs = 'directory', auto_open = False, auto_play = False)

def atualiza_service_worker(dados_cidade):
    data_anterior = dados_cidade.data.iat[-2].strftime('%d/%m/%Y')
    data_atual = dados_cidade.data.iat[-1].strftime('%d/%m/%Y')
    
    with open('docs/serviceWorker.js', 'r') as file :
      filedata = file.read()
    
    versao_anterior = int(filedata[16:18])
    
    #primeira atualização no dia
    if(filedata.count(data_atual) == 0):
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
    main()