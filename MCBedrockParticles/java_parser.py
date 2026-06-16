import json
import os


class JavaParticleParser:
    """
    Parses Minecraft Java Edition particle JSON files.

    Java particle JSONs live in assets/<namespace>/particles/<name>.json
    and have this simple format:

        {
            "textures": [
                "minecraft:glitter_0",
                "minecraft:glitter_1",
                ...
            ]
        }

    Each texture string resolves to:
        assets/<namespace>/textures/particle/<texture_name>.png
    """

    def __init__(self, filepath):
        self.filepath = filepath
        with open(filepath, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.textures_list = self.data.get("textures", self.data.get("values", []))
        if isinstance(self.textures_list, dict):
            self.textures_list = list(self.textures_list.values())
        elif isinstance(self.textures_list, str):
            self.textures_list = [self.textures_list]
            
        self.name = os.path.splitext(os.path.basename(filepath))[0]

    def get_identifier(self):
        return f"minecraft:{self.name}"

    def get_texture_paths(self):
        """
        Returns a list of resolved relative texture paths.
        e.g. ["textures/particle/glitter_0", "textures/glitter_1"]
        """
        paths = []
        for tex in self.textures_list:
            if ":" in tex:
                _, tex_name = tex.split(":", 1)
            else:
                tex_name = tex
                
            paths.append(tex_name)
        return paths

    def get_first_texture_path(self):
        """Returns just the first texture (for simple single-frame particles)."""
        paths = self.get_texture_paths()
        return paths[0] if paths else ""

    def get_frame_count(self):
        """Number of animation frames (textures listed)."""
        return len(self.textures_list)
