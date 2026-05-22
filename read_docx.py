from docx import Document
import sys

def extract_headings(file_path):
    try:
        doc = Document(file_path)
        print(f"Estrutura de {file_path}:")
        for para in doc.paragraphs:
            if para.style.name.startswith('Heading'):
                print(f"{para.style.name}: {para.text}")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    extract_headings(sys.argv[1])
