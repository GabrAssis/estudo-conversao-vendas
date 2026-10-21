"""Exercita a barreira de publicação em um índice Git real e isolado."""
import shutil
import subprocess
import sys
from pathlib import Path


def test_publicacao_aceita_sinteticos_e_bloqueia_alteracoes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    destino = tmp_path / "repo"
    shutil.copytree(root, destino, ignore=shutil.ignore_patterns(
        ".git", "outputs", "__pycache__", ".pytest_cache", ".venv"))

    def git(*args):
        subprocess.run(["git", *args], cwd=destino, check=True, capture_output=True)

    def verificar():
        return subprocess.run([sys.executable, "scripts/verificar_publicacao.py"],
                              cwd=destino, capture_output=True, text=True)

    git("init", "-q")
    git("add", ".")
    assert verificar().returncode == 0
    # Atualizar somente documentação deve validar também a base já versionada.
    git("-c", "user.name=Teste", "-c", "user.email=teste@localhost",
        "commit", "-qm", "Base sintética")
    readme = destino / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nDocumentação revisada.\n", encoding="utf-8")
    git("add", "README.md")
    assert verificar().returncode == 0
    relatorio = destino / "docs/relatorio.md"
    original_relatorio = relatorio.read_bytes()
    relatorio.write_bytes(original_relatorio + b"Resultado manual nao reproduzido.")
    git("add", "docs/relatorio.md")
    resultado = verificar()
    assert resultado.returncode == 2
    assert "Relatório staged" in resultado.stdout
    relatorio.write_bytes(original_relatorio)
    git("add", "docs/relatorio.md")
    imagem = destino / "docs/assets/motivos_perda.png"
    original = imagem.read_bytes()
    imagem.write_bytes(b"imagem externa")
    git("add", str(imagem.relative_to(destino)))
    resultado = verificar()
    assert resultado.returncode == 2
    assert "Imagem staged" in resultado.stdout
    imagem.write_bytes(original)
    csv = destino / "data/synthetic/conversao_sintetica.csv"
    csv.write_bytes(csv.read_bytes().replace(b"OP-000001", b"OP-999999", 1))
    git("add", ".")
    resultado = verificar()
    assert resultado.returncode == 2
    assert "EXATAMENTE" in resultado.stdout
