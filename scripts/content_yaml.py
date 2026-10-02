"""Readable YAML serialization for imported content."""

import yaml


class ContentDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)

    def choose_scalar_style(self):
        # Markdown hard breaks end in two spaces. PyYAML otherwise quotes the
        # entire paragraph and escapes its newlines, even with literal style.
        if self.event.style == "|" and not self.flow_level:
            return "|"
        return super().choose_scalar_style()


def represent_text(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


ContentDumper.add_representer(str, represent_text)


def dump_content(data):
    return yaml.dump(data, Dumper=ContentDumper, allow_unicode=True,
                     sort_keys=False, default_flow_style=False, width=110)
