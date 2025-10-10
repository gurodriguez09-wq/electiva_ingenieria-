import sqlite3
import hashlib
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

def generar_codigo_hash(titulo, anio):
    titulo_procesado = titulo.lower().replace(" ", "")
    cadena = titulo_procesado + str(anio)
    codigo = hashlib.sha256(cadena.encode()).hexdigest()
    return codigo

def inicializar_bd():
    conn = sqlite3.connect("cine.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            clave TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS peliculas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            anio INTEGER,
            sinopsis TEXT,
            director TEXT,
            elenco TEXT,
            genero TEXT,
            codigo_hash TEXT UNIQUE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS resenas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pelicula_id INTEGER,
            usuario TEXT,
            calificacion INTEGER,
            resena TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pelicula_id) REFERENCES peliculas(id)
        )
    """)

    c.execute("SELECT COUNT(*) FROM peliculas")
    if c.fetchone()[0] == 0:
        peliculas = [
            ("El Padrino", 1972, "La historia de la familia Corleone, una poderosa familia mafiosa de Nueva York.", "Francis Ford Coppola", "Marlon Brando, Al Pacino, James Caan", "Drama, Crimen"),
            ("Interestelar", 2014, "Un grupo de exploradores viaja a través de un agujero de gusano en el espacio para asegurar la supervivencia de la humanidad.", "Christopher Nolan", "Matthew McConaughey, Anne Hathaway, Jessica Chastain", "Ciencia Ficción, Drama"),
            ("Inception", 2010, "Un ladrón que roba secretos corporativos a través del uso de la tecnología de compartir sueños recibe la tarea inversa de plantar una idea.", "Christopher Nolan", "Leonardo DiCaprio, Joseph Gordon-Levitt, Ellen Page", "Ciencia Ficción, Acción"),
            ("Matrix", 1999, "Un hacker descubre que la realidad que conoce es una simulación creada por máquinas inteligentes.", "Lana Wachowski, Lilly Wachowski", "Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss", "Ciencia Ficción, Acción"),
            ("Pulp Fiction", 1994, "Varias historias entrelazadas de crimen en Los Ángeles.", "Quentin Tarantino", "John Travolta, Uma Thurman, Samuel L. Jackson", "Crimen, Drama"),
            ("Forrest Gump", 1994, "La vida de un hombre simple con un corazón puro que vive eventos extraordinarios.", "Robert Zemeckis", "Tom Hanks, Robin Wright, Gary Sinise", "Drama, Romance"),
            ("El Caballero de la Noche", 2008, "Batman enfrenta al Joker en una batalla por el alma de Gotham.", "Christopher Nolan", "Christian Bale, Heath Ledger, Aaron Eckhart", "Acción, Crimen"),
            ("Titanic", 1997, "Una historia de amor en el trágico viaje del Titanic.", "James Cameron", "Leonardo DiCaprio, Kate Winslet, Billy Zane", "Romance, Drama")
        ]
        for pelicula in peliculas:
            titulo, anio, sinopsis, director, elenco, genero = pelicula
            codigo_hash = generar_codigo_hash(titulo, anio)
            c.execute("INSERT INTO peliculas (titulo, anio, sinopsis, director, elenco, genero, codigo_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (titulo, anio, sinopsis, director, elenco, genero, codigo_hash))

    conn.commit()
    conn.close()

inicializar_bd()

class Servidor(BaseHTTPRequestHandler):

    def enviar_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            archivo = "index.html"
        elif path == "/registro" or path == "/registro.html":
            archivo = "registro.html"
        elif path == "/peliculas" or path == "/peliculas.html":
            archivo = "peliculas.html"
        elif path == "/api/peliculas":
            from urllib.parse import parse_qs
            query_params = parse_qs(parsed.query)
            busqueda = query_params.get('busqueda', [''])[0]
            self.listar_peliculas(busqueda)
            return
        elif path.startswith("/api/resenas/"):
            pelicula_id = path.split("/")[-1]
            self.obtener_resenas(pelicula_id)
            return
        else:
            self.send_error(404, "Archivo no encontrado")
            return

        if os.path.exists(archivo):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            with open(archivo, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "Archivo no encontrado")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data.decode())
        except json.JSONDecodeError:
            self.enviar_json({"error": "JSON inválido"}, 400)
            return

        if path == "/api/registro":
            nombre = data.get("nombre")
            clave = data.get("clave")

            if not nombre or not clave:
                self.enviar_json({"error": "Faltan campos"}, 400)
                return

            clave_hash = hashlib.sha256(clave.encode()).hexdigest()

            conn = sqlite3.connect("cine.db")
            c = conn.cursor()
            try:
                c.execute("INSERT INTO usuarios (nombre, clave) VALUES (?, ?)", (nombre, clave_hash))
                conn.commit()
                self.enviar_json({"mensaje": "Registro exitoso"})
            except sqlite3.IntegrityError:
                self.enviar_json({"error": "Usuario ya existe"}, 400)
            finally:
                conn.close()


        elif path == "/api/login":
            nombre = data.get("nombre")
            clave = data.get("clave")

            if not nombre or not clave:
                self.enviar_json({"error": "Faltan campos"}, 400)
                return

            conn = sqlite3.connect("cine.db")
            c = conn.cursor()
            c.execute("SELECT clave FROM usuarios WHERE nombre=?", (nombre,))
            fila = c.fetchone()
            conn.close()

            if not fila:
                self.enviar_json({"error": "Usuario no encontrado"}, 401)
                return

            clave_hash = hashlib.sha256(clave.encode()).hexdigest()
            if clave_hash != fila[0]:
                self.enviar_json({"error": "Clave incorrecta"}, 401)
                return

            self.enviar_json({"mensaje": "Inicio de sesión exitoso"}, 200)

        elif path == "/api/peliculas":
            titulo = data.get("titulo")
            anio = data.get("anio")
            director = data.get("director")
            elenco = data.get("elenco")
            sinopsis = data.get("sinopsis")
            genero = data.get("genero")

            if not all([titulo, anio, director, elenco, sinopsis, genero]):
                self.enviar_json({"error": "Todos los campos son obligatorios"}, 400)
                return

            try:
                anio = int(anio)
            except ValueError:
                self.enviar_json({"error": "El año debe ser un número válido"}, 400)
                return

            conn = sqlite3.connect("cine.db")
            c = conn.cursor()
            
            titulo_sin_espacios = titulo.lower().replace(" ", "")
            c.execute("SELECT titulo, anio FROM peliculas")
            peliculas_existentes = c.fetchall()
            
            for pelicula_titulo, pelicula_anio in peliculas_existentes:
                titulo_existente_sin_espacios = pelicula_titulo.lower().replace(" ", "")
                if titulo_sin_espacios == titulo_existente_sin_espacios:
                    conn.close()
                    self.enviar_json({
                        "error": f"Ya existe una película con el mismo nombre: '{pelicula_titulo}' ({pelicula_anio})"
                    }, 400)
                    return
            
            codigo_hash = generar_codigo_hash(titulo, anio)
            
            try:
                c.execute("""INSERT INTO peliculas (titulo, anio, director, elenco, sinopsis, genero, codigo_hash) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                         (titulo, anio, director, elenco, sinopsis, genero, codigo_hash))
                conn.commit()
                pelicula_id = c.lastrowid
                self.enviar_json({
                    "mensaje": "Película añadida exitosamente",
                    "pelicula": {
                        "id": pelicula_id,
                        "titulo": titulo,
                        "anio": anio,
                        "director": director,
                        "elenco": elenco,
                        "sinopsis": sinopsis,
                        "genero": genero,
                        "codigo_hash": codigo_hash
                    }
                })
            except Exception as e:
                self.enviar_json({"error": str(e)}, 500)
            finally:
                conn.close()

        elif path == "/api/resenas":
            pelicula_id = data.get("pelicula_id")
            usuario = data.get("usuario")
            calificacion = data.get("calificacion")
            resena = data.get("resena")

            if not all([pelicula_id, usuario, calificacion, resena]):
                self.enviar_json({"error": "Faltan campos"}, 400)
                return

            if not isinstance(calificacion, int) or calificacion < 1 or calificacion > 5:
                self.enviar_json({"error": "La calificación debe ser entre 1 y 5"}, 400)
                return

            palabras_procesadas = []
            for palabra in resena.split():
                if any(c.isupper() for c in palabra):
                    palabras_procesadas.append(palabra.lower())
                else:
                    palabras_procesadas.append(palabra)
            resena_procesada = " ".join(palabras_procesadas)

            conn = sqlite3.connect("cine.db")
            c = conn.cursor()
            try:
                c.execute("INSERT INTO resenas (pelicula_id, usuario, calificacion, resena) VALUES (?, ?, ?, ?)",
                          (pelicula_id, usuario, calificacion, resena_procesada))
                conn.commit()
                self.enviar_json({"mensaje": "Reseña añadida exitosamente", "resena_procesada": resena_procesada})
            except Exception as e:
                self.enviar_json({"error": str(e)}, 500)
            finally:
                conn.close()

        else:
            self.enviar_json({"error": "Ruta no encontrada"}, 404)

    def listar_peliculas(self, busqueda=""):
        conn = sqlite3.connect("cine.db")
        c = conn.cursor()
        
        if busqueda:
            busqueda_lower = busqueda.lower()
            c.execute("""
                SELECT id, titulo, anio, sinopsis, director, elenco, genero, codigo_hash 
                FROM peliculas 
                WHERE LOWER(titulo) LIKE ? 
                   OR LOWER(director) LIKE ? 
                   OR LOWER(genero) LIKE ? 
                   OR CAST(anio AS TEXT) LIKE ?
            """, (f"%{busqueda_lower}%", f"%{busqueda_lower}%", f"%{busqueda_lower}%", f"%{busqueda}%"))
        else:
            c.execute("SELECT id, titulo, anio, sinopsis, director, elenco, genero, codigo_hash FROM peliculas")
        
        peliculas = [{"id": id, "titulo": t, "anio": a, "sinopsis": s, "director": d, "elenco": e, "genero": g, "codigo_hash": ch} 
                     for id, t, a, s, d, e, g, ch in c.fetchall()]
        conn.close()
        self.enviar_json(peliculas)

    def obtener_resenas(self, pelicula_id):
        conn = sqlite3.connect("cine.db")
        c = conn.cursor()
        c.execute("SELECT usuario, calificacion, resena, fecha FROM resenas WHERE pelicula_id=? ORDER BY fecha DESC", (pelicula_id,))
        resenas = [{"usuario": u, "calificacion": cal, "resena": r, "fecha": f} for u, cal, r, f in c.fetchall()]
        conn.close()
        self.enviar_json(resenas)

if __name__ == "__main__":
    puerto = 8000
    print(f"Servidor REST ejecutandose en http://localhost:{puerto}")
    httpd = HTTPServer(("localhost", puerto), Servidor)
    httpd.serve_forever()
