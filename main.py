from flask import Flask, request, send_file, jsonify, url_for
from jinja2 import Environment, FileSystemLoader
import os
import cairosvg
import tempfile
from PIL import Image
import io
import uuid

app = Flask(__name__)

template_names = [
    "cover.svg",
    "slide1.svg",
    "slide2.svg",
    "slide3.svg",
    "slide4.svg",
    "slide5.svg",
    "zbackcover.svg", # Esta plantilla es estática, no usa datos del JSON.
]

@app.route("/generate", methods=["POST"])
def generate():
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No data provided"}), 400

        if 'carousel' not in payload:
            return jsonify({"error": "Invalid JSON structure: 'carousel' key missing"}), 400
        carousel_data = payload['carousel']

        # Obtenemos el array de slides. El 'cover_title' ya no se extrae ni se pasa.
        json_slides_array = carousel_data.get('slides', [])

        # Obtener el nombre del set de templates desde el request (POST JSON o query param), default 'rebound'
        template_set = None
        if request.is_json:
            template_set = request.json.get('template')
        if not template_set:
            template_set = request.args.get('template', 'rebound')
        if not template_set:
            template_set = 'rebound'

        # Path absoluto a la subcarpeta del template set
        templates_folder = os.path.join('templates', template_set)

        if not os.path.isdir(templates_folder):
            return jsonify({"error": f"Template set '{template_set}' does not exist."}), 400

        env = Environment(loader=FileSystemLoader(templates_folder))
        output_files = []

        # Crear carpeta temporal única para esta generación
        unique_id = str(uuid.uuid4())
        gen_dir = os.path.join(tempfile.gettempdir(), f"gen_{unique_id}")
        os.makedirs(gen_dir, exist_ok=True)

        for i, template_file_name in enumerate(template_names):
            try:
                template = env.get_template(template_file_name)
            except Exception as e:
                app.logger.error(f"Template '{template_file_name}' not found in set '{template_set}': {e}")
                return jsonify({"error": f"Template '{template_file_name}' not found in set '{template_set}'"}), 400
            data_for_render = {}  # Por defecto, el contexto de datos estará vacío.

            if template_file_name == "zbackcover.svg":
                # zbackcover.svg es estático, no necesita datos del JSON.
                app.logger.info(f"Rendering '{template_file_name}' as a static template (no dynamic JSON data).")
            elif i < len(json_slides_array):
                # Para "cover.svg", "slide1.svg", ..., "slide5.svg"
                # Estos SÍ esperan datos del array 'json_slides_array'
                slide_content_wrapper = json_slides_array[i]
                template_base_name = os.path.splitext(template_file_name)[0]
                
                if template_base_name in slide_content_wrapper:
                    data_for_render = slide_content_wrapper[template_base_name].copy()
                else:
                    # Si para un slide específico no se encuentra la clave esperada (ej: "slide1")
                    # se loguea una advertencia y se renderiza con datos vacíos para esa parte.
                    app.logger.warning(
                        f"Data key '{template_base_name}' not found in JSON slide at index {i} "
                        f"for template '{template_file_name}'. Rendering with empty dynamic data for this slide."
                    )
            else:
                # Este caso cubre plantillas (que no sean zbackcover.svg) que estén en `template_names`
                # pero para las cuales no haya un elemento correspondiente en `json_slides_array`
                # (por ejemplo, si `json_slides_array` es más corto de lo esperado).
                app.logger.warning(
                    f"No data found in 'slides' array for template '{template_file_name}' (index {i}). "
                    f"The 'slides' array has {len(json_slides_array)} elements. "
                    f"Rendering with empty dynamic data for this slide."
                )
            
            # Descomenta la siguiente línea si quieres ver en los logs qué datos se pasan a cada plantilla:
            # app.logger.debug(f"Rendering '{template_file_name}' with data: {data_for_render}")

            rendered_svg = template.render(data_for_render)

            output_filename = f"{os.path.splitext(template_file_name)[0]}.jpg"
            output_path = os.path.join(gen_dir, output_filename)

            # Convert SVG to PNG in memory first
            png_data = cairosvg.svg2png(
                bytestring=rendered_svg.encode("utf-8"),
                dpi=300
            )
            
            # Convert PNG to JPG using PIL
            png_image = Image.open(io.BytesIO(png_data))
            # Convert to RGB if it has transparency (RGBA)
            if png_image.mode in ('RGBA', 'LA'):
                # Create a white background
                rgb_image = Image.new('RGB', png_image.size, (255, 255, 255))
                if png_image.mode == 'RGBA':
                    rgb_image.paste(png_image, mask=png_image.split()[-1])  # Use alpha channel as mask
                else:
                    rgb_image.paste(png_image)
                png_image = rgb_image
            elif png_image.mode != 'RGB':
                png_image = png_image.convert('RGB')
            
            # Save as JPG
            png_image.save(output_path, 'JPEG', quality=95)

            output_files.append({
                "name": output_filename,
                "gen_id": unique_id
            })

        return jsonify({
            "generated": [f["name"] for f in output_files],
            "gen_id": unique_id
        }), 200

    except Exception as e:
        app.logger.error(f"Error processing /generate request: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error al procesar: {str(e)}"}), 500

@app.route("/download/<gen_id>/<filename>", methods=["GET"])
def download(gen_id, filename):
    gen_dir = os.path.join(tempfile.gettempdir(), f"gen_{gen_id}")
    file_path = os.path.join(gen_dir, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "Archivo no encontrado"}), 404

@app.route("/get-public-url/<gen_id>/<filename>", methods=["GET"])
def get_public_url(gen_id, filename):
    """
    Returns a public URL for downloading the image instead of serving the file directly.
    This endpoint provides a JSON response with the public URL.
    """
    gen_dir = os.path.join(tempfile.gettempdir(), f"gen_{gen_id}")
    file_path = os.path.join(gen_dir, filename)
    if os.path.exists(file_path):
        public_url = url_for('serve_image', gen_id=gen_id, filename=filename, _external=True)
        return jsonify({
            "filename": filename,
            "public_url": public_url,
            "status": "available"
        }), 200
    return jsonify({"error": "Archivo no encontrado"}), 404

@app.route("/serve/<gen_id>/<filename>", methods=["GET"])
def serve_image(gen_id, filename):
    """
    Serves the image file directly (used by the public URL).
    This endpoint serves the file without forcing download.
    """
    gen_dir = os.path.join(tempfile.gettempdir(), f"gen_{gen_id}")
    file_path = os.path.join(gen_dir, filename)
    if os.path.exists(file_path):
        return send_file(file_path, mimetype='image/jpeg')
    return jsonify({"error": "Archivo no encontrado"}), 404

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)