from flask import Flask, request, send_file, jsonify
from jinja2 import Environment, FileSystemLoader
import os
import cairosvg
import tempfile

app = Flask(__name__)

template_names = [
    "cover.svg",
    "slide1.svg",
    "slide2.svg",
    "slide3.svg",
    "slide4.svg",
    "slide5.svg",
    "zbackcover.svg",
]

@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        env = Environment(loader=FileSystemLoader("templates"))
        output_files = []

        for template_name in template_names:
            template = env.get_template(template_name)
            rendered_svg = template.render(data)

            output_filename = f"{os.path.splitext(template_name)[0]}.png"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)

            # 🔧 Corrección: Eliminar 'font_config'
            cairosvg.svg2png(
                bytestring=rendered_svg.encode("utf-8"),
                write_to=output_path,
                dpi=300
            )

            output_files.append({
                "name": output_filename,
                "path": output_path
            })

        return jsonify({"generated": [f["name"] for f in output_files]}), 200

    except Exception as e:
        return jsonify({"error": f"Error al procesar: {str(e)}"}), 500

@app.route("/download/<filename>", methods=["GET"])
def download(filename):
    file_path = os.path.join(tempfile.gettempdir(), filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "Archivo no encontrado"}), 404

if __name__ == "__main__":
    app.run(debug=True, port=5000)
