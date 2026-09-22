import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_svg import validate_svg


class PortableSvgTests(unittest.TestCase):
    def check(self, body, extra=''):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'figure.svg'
            path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" {extra}><title>A test diagram</title>{body}</svg>')
            return validate_svg(path)

    def test_editable_local_shapes_and_markers(self):
        self.assertTrue(self.check('<defs><marker id="arrow"><path d="M0 0L3 3"/></marker></defs><path d="M0 0L80 80" marker-end="url(#arrow)"/><text x="2" y="12">Decision</text>'))

    def test_rejects_bitmap_script_external_and_foreign_nodes(self):
        for body in ['<image href="data:image/png;base64,x"/>', '<script>alert(1)</script>', '<use href="https://example.test/a.svg"/>', '<foreignObject/>', '<style>@import "x";</style>']:
            with self.subTest(body=body), self.assertRaises(ValueError): self.check(body)

    def test_rejects_event_handlers_and_external_paints(self):
        for body in ['<path onclick="alert(1)"/>', '<path fill="url(https://example.test/a)"/>', '<path style="fill:red"/>']:
            with self.subTest(body=body), self.assertRaises(ValueError): self.check(body)

    def test_requires_accessible_title_and_valid_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bad.svg'
            for viewbox in ['0 0 -1 100', '0 0 nan 100', '0 0 100', '0 0 inf 100']:
                path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}"><title>Diagram</title></svg>')
                with self.subTest(viewbox=viewbox), self.assertRaises(ValueError): validate_svg(path)
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"/>')
            with self.assertRaises(ValueError): validate_svg(path)


if __name__ == '__main__': unittest.main()
