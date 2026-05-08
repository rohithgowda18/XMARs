import os
import sys

def print_tree(startpath, exclude_dirs, f_out):
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        level = root.replace(startpath, '').count(os.sep)
        if level == 0:
            f_out.write(f"{os.path.basename(root)}/\n")
        else:
            indent = '│   ' * (level - 1) + '├── '
            f_out.write(f"{indent}{os.path.basename(root)}/\n")
        
        sub_indent = '│   ' * level + '├── '
        for f in files:
            f_out.write(f"{sub_indent}{f}\n")

if __name__ == "__main__":
    project_root = os.getcwd()
    exclude = {'.venv', 'venv', 'node_modules', '.git', '__pycache__', 'dist', 'build'}
    with open("project_tree_full.txt", "w", encoding="utf-8") as f:
        print_tree(project_root, exclude, f)
