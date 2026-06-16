import os
import re
import subprocess
import sys

def main():
    print("Preparing to publish new update...")
    
    init_path = os.path.join("MCBedrockParticles", "__init__.py")
    if not os.path.exists(init_path):
        print("Error: Could not find __init__.py!")
        sys.exit(1)
        
    with open(init_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Find version
    match = re.search(r'\"version\":\s*\(\s*(\d+),\s*(\d+),\s*(\d+)\s*\)', content)
    if not match:
        print("Error: Could not parse version from bl_info!")
        sys.exit(1)
        
    v1, v2, v3 = match.groups()
    new_patch = int(v3) + 1
    old_version_str = match.group(0)
    new_version_str = f'"version": ({v1}, {v2}, {new_patch})'
    
    content = content.replace(old_version_str, new_version_str)
    
    with open(init_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Bumped version from {v1}.{v2}.{v3} -> {v1}.{v2}.{new_patch}")
    
    # Repack the zip
    print("Building plugin ZIP...")
    subprocess.run([sys.executable, "pack_zip.py"], check=True)
    
    print("\n" + "="*50)
    print("SUCCESS! Update packed and ready for release.")
    print("="*50)
    print("To publish this update to your users:")
    print(f"1. Go to your GitHub repository -> Releases -> Draft a new release")
    print(f"2. Set the tag name to: v{v1}.{v2}.{new_patch}")
    print(f"3. Set the release title to: Release v{v1}.{v2}.{new_patch}")
    print(f"4. Drag and drop 'MCBedrockParticles_Release.zip' into the binaries area.")
    print(f"5. Click 'Publish release'!")
    print("\nUsers will automatically download this new version if they click 'Check for Updates' inside Blender.")

if __name__ == "__main__":
    main()
