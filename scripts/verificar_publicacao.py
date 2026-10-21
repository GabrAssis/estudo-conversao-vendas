"""Barrreira de publicação: valida arquivos staged e bytes de dados fictícios.

Execute DEPOIS de `git add .` e ANTES de `git commit`.
As regras de allowlist são conservadoras; revisar manualmente é obrigatório.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARQUIVOS_PERMITIDOS = set(['.gitignore', '.gitattributes', 'README.md', 'requirements.txt', 'conversao_produto.py', 'scripts/gerar_dados_sinteticos.py', 'scripts/verificar_publicacao.py', 'utilitarios.py', 'tests/test_conversao.py', 'data/synthetic/conversao_sintetica.csv'])
CAMINHO_SINTETICO = 'data/synthetic/conversao_sintetica.csv'


def git(*args: str) -> bytes:
    return subprocess.run(['git', *args], cwd=ROOT, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def validar() -> list[str]:
    falhas = []
    try:
        git('rev-parse', '--is-inside-work-tree')
        arquivos = [s.decode() for s in git('diff', '--cached', '--name-only', '-z').split(b'\0') if s]
        if not arquivos:
            return ['Nenhum arquivo staged. Primeiro use git add . e execute novamente.']
        def ler(nome):
            return git('show', ':'+nome)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ['Inicie um repositório Git, faça git add . e execute a verificação novamente.']

    for nome in arquivos:
        if nome not in ARQUIVOS_PERMITIDOS:
            falhas.append('Arquivo não autorizado para publicação: '+nome)
            continue
        try:
            dado = ler(nome)
        except subprocess.CalledProcessError:
            falhas.append('Arquivo staged inacessível: '+nome)
            continue
        if nome.endswith(('.py', '.md', '.txt', '.csv', '.gitattributes', '.gitignore')):
            content = dado.decode('utf-8-sig', errors='replace')
            # Padrões típicos de identificadores pessoais e segredos colados.
            for padrao, rotulo in [
                (r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', 'CPF'),
                (r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b', 'CNPJ'),
                (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', 'email'),
                (r'(?im)^\s*(?:API_KEY|SECRET_KEY|ACCESS_TOKEN|DATABASE_URL)\s*=\s*[^#\s]', 'credencial'),
            ]:
                if re.search(padrao, content):
                    falhas.append(f'{rotulo} suspeito em: {nome}')
    if CAMINHO_SINTETICO not in arquivos:
        falhas.append('Base sintética não está staged: '+CAMINHO_SINTETICO)
    else:
        sys.path.insert(0, str(ROOT))
        from scripts.gerar_dados_sinteticos import gerar
        buffer = io.BytesIO()
        gerar().to_csv(buffer, index=False, encoding='utf-8-sig', lineterminator='\n')
        if ler(CAMINHO_SINTETICO) != buffer.getvalue():
            falhas.append('A base staged não coincide EXATAMENTE com o gerador sintético: '+CAMINHO_SINTETICO)
    return falhas


if __name__ == '__main__':
    problemas = validar()
    if problemas:
        print('BLOQUEADO: revisão obrigatória antes da publicação.')
        for problema in problemas:
            print('- '+problema)
        sys.exit(2)
    print('Verificação passou: staged dentro da allowlist; base sintética íntegra.')
    print('Revise manualmente as alterações antes de publicar.')
