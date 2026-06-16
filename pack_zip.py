import zipfile
import os

source_dir = r"c:\Users\MrRob\Downloads\Blender Particles plugin\MCBedrockParticles"
zip_path = r"c:\Users\MrRob\Downloads\Blender Particles plugin\MCBedrockParticles_Release.zip"

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(source_dir):
        if '__pycache__' in root:
            continue
        rel_root = os.path.relpath(root, source_dir)
        if rel_root != '.':
            zf.write(root, rel_root)
        for file in files:
            if file.endswith('.pyc'):
                continue
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, source_dir)
            zf.write(file_path, rel_path)
print("Created extension zip")
