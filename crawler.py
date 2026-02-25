import pathlib

def crawl_repository(root_path=".", output_file="repo_context.txt"):
    root = pathlib.Path(root_path)
    # Define files/folders to ignore (Tamasic/Heavy noise)
    ignore_list = {'.git', '.venv', '__pycache__', 'osis_strategic_archives.db'}
    # Define extensions we actually want to read
    valid_extensions = {'.py', '.json', '.txt', '.md', '.yaml', '.sh'}

    print(f"--- 🏛️ Crawling Repository: {root.absolute()} ---")
    
    with open(output_file, "w", encoding="utf-8") as f:
        for path in root.rglob('*'):
            # Skip ignored directories and hidden files
            if any(part in ignore_list or part.startswith('.') for part in path.parts):
                continue
            
            if path.is_file() and path.suffix in valid_extensions:
                try:
                    content = path.read_text(encoding='utf-8')
                    f.write(f"\n{'='*80}\n")
                    f.write(f"FILE: {path}\n")
                    f.write(f"{'='*80}\n\n")
                    f.write(content)
                    f.write("\n")
                    print(f"✅ Read: {path}")
                except Exception as e:
                    print(f"⚠️  Could not read {path}: {e}")

    print(f"\n✅ Repository context saved to: {output_file}")

if __name__ == "__main__":
    crawl_repository()