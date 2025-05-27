from flask import Flask, request, send_file, jsonify, url_for
from jinja2 import Environment, FileSystemLoader
import os
import cairosvg
import tempfile
from PIL import Image
import io

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

        env = Environment(loader=FileSystemLoader("templates"))
        output_files = []

        for i, template_file_name in enumerate(template_names):
            template = env.get_template(template_file_name)
            data_for_render = {} # Por defecto, el contexto de datos estará vacío.

            if template_file_name == "zbackcover.svg":
                # zbackcover.svg es estático, no necesita datos del JSON.
                # Se renderizará con un contexto vacío.
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
            output_path = os.path.join(tempfile.gettempdir(), output_filename)

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
            })

        return jsonify({"generated": [f["name"] for f in output_files]}), 200

    except Exception as e:
        app.logger.error(f"Error processing /generate request: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error al procesar: {str(e)}"}), 500

@app.route("/download/<filename>", methods=["GET"])
def download(filename):
    file_path = os.path.join(tempfile.gettempdir(), filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "Archivo no encontrado"}), 404

@app.route("/get-public-url/<filename>", methods=["GET"])
def get_public_url(filename):
    """
    Returns a public URL for downloading the image instead of serving the file directly.
    This endpoint provides a JSON response with the public URL.
    """
    file_path = os.path.join(tempfile.gettempdir(), filename)
    if os.path.exists(file_path):
        # Generate the public URL using url_for
        public_url = url_for('serve_image', filename=filename, _external=True)
        return jsonify({
            "filename": filename,
            "public_url": public_url,
            "status": "available"
        }), 200
    return jsonify({"error": "Archivo no encontrado"}), 404

@app.route("/serve/<filename>", methods=["GET"])
def serve_image(filename):
    """
    Serves the image file directly (used by the public URL).
    This endpoint serves the file without forcing download.
    """
    file_path = os.path.join(tempfile.gettempdir(), filename)
    if os.path.exists(file_path):
        return send_file(file_path, mimetype='image/jpeg')
    return jsonify({"error": "Archivo no encontrado"}), 404

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)