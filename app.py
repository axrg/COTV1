from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from datetime import datetime
import pytz
import cloudinary.uploader
from config import *
import re
from config import api_secret
from authlib.integrations.flask_client import OAuth
import uuid
from functools import wraps
from flask import session, redirect, url_for

app = Flask(__name__)
app.secret_key = api_secret

# Configuración de OAuth
oauth = OAuth(app)

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://avnadmin:AVNS_jiyfeiP_1IrO2xouEYS@mysql-100c3e11-datascience.k.aivencloud.com:28460/cotizaciones'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'ssl': {
            'ca': 'ca.pem'  
        }
    }
}

# Inicializa la extensión
db = SQLAlchemy(app)

clientez = None
infoz = None



def requiere_login(func):
    @wraps(func)
    def verificar_login(*args, **kwargs):
        if 'user' not in session:
            # Si el usuario no está autenticado, redirigir a la página de login
            return redirect(url_for('autenticacion'))
        return func(*args, **kwargs)
    return verificar_login

class Cotizacion(db.Model):
    # Atributos base
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=lambda: datetime.now(pytz.timezone('America/Bogota')).date())
    ciudad = db.Column(db.String(100), nullable=False)
    empresa = db.Column(db.String(100), nullable=False)
    proyecto = db.Column(db.String(100), nullable=False)
    plazo = db.Column(db.String(100), nullable=False)
    entrega = db.Column(db.String(100), nullable=False)
    anticipo = db.Column(db.Integer, nullable=False)
    p_acta = db.Column(db.Integer, nullable=False)
    f_acta = db.Column(db.Integer, nullable=False)
    consecutivo = db.Column(db.Integer, nullable=False)
    # Relación auto-referencial para versiones
    version_padre_id = db.Column(db.Integer, db.ForeignKey('cotizacion.id'), nullable=True)
    versiones = db.relationship('Cotizacion', backref=db.backref('version_padre', remote_side=[id]), lazy=True)
    # Atributos definibles por el usuario
    # Relación con CotizacionProducto
    productos_detalle = db.relationship('CotizacionProducto', backref='cotizacion', lazy=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    cliente = db.relationship('Cliente', backref=db.backref('cotizaciones', lazy=True))
    servicio = db.Column(db.String(1000), nullable=False, default="v")
    #documentos = db.relationship('Document', backref='cotizacion', lazy=True)

    def __repr__(self):
        return f'<Cotizacion {self.id} - Cliente: {self.cliente} - Empresa: {self.empresa}>'


class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    celular = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    # Relación con Cotizacion
    """
    cotizacion_id = db.Column(db.Integer, db.ForeignKey('cotizacion.id'))
    cotizaciones = db.relationship('Cotizacion', back_populates='clienten', order_by='Cotizacion.id')
    """

    def __repr__(self):
        return f'<Cliente {self.nombre}>'


class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    # cotizacion_id = db.Column(db.Integer, db.ForeignKey('cotizacion.id'), nullable=False)
    # cotizacion = db.relationship('Cotizacion', backref=db.backref('productos', lazy=True))

    def __repr__(self):
        return f'<Producto {self.nombre}>'


class CotizacionProducto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cotizacion_id = db.Column(db.Integer, db.ForeignKey('cotizacion.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)

    cantidad = db.Column(db.Integer, nullable=False)
    tamano = db.Column(db.Integer, nullable=False)

    producto = db.relationship('Producto', backref=db.backref('cotizacion_producto', lazy=True))

    def __repr__(self):
        return f'<CotizacionProducto: Producto {self.producto.nombre}, Cantidad: {self.cantidad}, Tamaño: {self.tamano}>'

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(255), nullable=False)
    fecha_subida = db.Column(db.DateTime, nullable=False)
    cotizacion_id = db.Column(db.Integer, db.ForeignKey('cotizacion.id'), nullable=False)
    
    cotizacion = db.relationship('Cotizacion', backref='documentos')

    def __repr__(self):
        return f'<Document: Nombre {self.nombre}, URL: {self.url}, Proyecto: {self.proyecto}>'
    
@app.route('/index')
@requiere_login
def index():
    return render_template('index.html')


@app.route('/')
@requiere_login
def acceso():
    # Verificar si el usuario está autenticado
    user = session.get('user')
    if not user:
        # Si el usuario no está autenticado, redirigir a la página de login
        return redirect(url_for('autenticacion'))

    # Si el usuario está autenticado, mostrar la página de acceso
    return render_template('acceso.html', user=user)

# Ruta para mostrar la página de autenticación
@app.route('/autenticacion')
def autenticacion():
    # Verificar si el usuario ya está logueado
    user = session.get('user')
    if user:
        return redirect(url_for('index'))  # Si ya está logueado, redirigir a index

    return render_template('autenticacion.html')  # Mostrar la página de autenticación

# Ruta para iniciar sesión con Google
@app.route('/google/')
def google():
    # Configurar las credenciales de Google OAuth
    GOOGLE_CLIENT_ID = '725036199104-1bl81bconpj40ejamq4m993e63s89r7f.apps.googleusercontent.com'
    GOOGLE_CLIENT_SECRET = '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'

    # URL de configuración de OpenID de Google
    CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url=CONF_URL,
        client_kwargs={'scope': 'openid email profile'}
    )

    # Generar un nonce único para esta solicitud
    nonce = str(uuid.uuid4())
    session['nonce'] = nonce  # Guardar el nonce en la sesión

    # Redirigir a la página de autorización de Google con el nonce
    redirect_uri = url_for('google_auth', _external=True)
    print(f"Redirecting with nonce: {nonce}")  # Depuración: imprime el nonce generado

    # Asegúrate de pasar el nonce aquí
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce)

# Ruta de callback después de la autenticación de Google
@app.route('/google/auth/')
def google_auth():
    # Obtener el token y los datos del usuario de Google
    token = oauth.google.authorize_access_token()

    # Recuperar el nonce guardado en la sesión
    nonce = session.pop('nonce', None)
    if not nonce:
        return 'Nonce missing in session', 400

    # Parsear el id_token de Google con el nonce
    user = oauth.google.parse_id_token(token, nonce=nonce)

    # Guardar los datos del usuario en la sesión
    session['user'] = user

    print("Google User:", user)

    # Redirigir al index después de la autenticación
    return redirect('/')

@app.route('/lista_proyectos')
@requiere_login
def lista_proyectos():
    # Consulta todas las cotizaciones
    cotizaciones = Cotizacion.query.all()

    # Consulta todos los documentos
    documentos = Document.query.all()

    # Usar un diccionario para evitar proyectos duplicados
    proyectos_unicos = {}

    for cotizacion in cotizaciones:
        # Filtrar documentos por proyecto
        docs_asociados = []
        for documento in documentos:
            if documento.cotizacion_id == cotizacion.id:
                docs_asociados.append(documento)

        if docs_asociados:  # Si hay documentos asociados
            # Solo agregar una vez el proyecto, usando 'proyecto' como clave
            if cotizacion.proyecto not in proyectos_unicos:
                proyectos_unicos[cotizacion.proyecto] = {
                    "cotizacion": cotizacion,
                    "documentos": docs_asociados
                }

    # Enviar la lista de cotizaciones únicas
    return render_template('lista_proyectos.html', cotizaciones=list(proyectos_unicos.values()))


def extract_public_id(url):
    # Extraer el public_id de la URL de Cloudinary
    match = re.search(r'/v\d+/(.+?)\.\w+', url)
    if match:
        return match.group(1)
    return None

@app.route('/reemplazar_archivo', methods=['POST'])
@requiere_login
def reemplazar_archivo():
    nombreArchivoReemplazar = request.form['nombreArchivoReemplazar']
    archivoNuevo = request.files['archivoNuevo']
    cotizacionid = request.form['cotizacion_id']
    
    if archivoNuevo:
        try:
            documento_existente = Document.query.filter_by(nombre=nombreArchivoReemplazar, cotizacion_id=cotizacionid).first()
            if documento_existente:
                # Extraer el public_id de la URL existente
                public_id = extract_public_id(documento_existente.url)
                if public_id:
                    # Eliminar el archivo anterior de Cloudinary
                    cloudinary.uploader.destroy(public_id)

                # Subir el nuevo archivo a Cloudinary
                resultado = cloudinary.uploader.upload(archivoNuevo, secure=True)
                documento_existente.url = resultado['secure_url']
                documento_existente.nombre = archivoNuevo.filename

                db.session.commit()
                flash('Archivo reemplazado exitosamente', 'success')
            else:
                flash('El archivo a reemplazar no existe', 'error')
        except Exception as e:
            flash(f'Error al reemplazar el archivo: {str(e)}', 'error')
    else:
        flash('No se seleccionó ningún archivo', 'error')
    
    return redirect(url_for('listar_documentos', cotizacionid=documento_existente.cotizacion_id))

@app.route('/eliminar_archivo', methods=['POST'])
@requiere_login
def eliminar_archivo():
    nombreArchivoEliminar = request.form['nombreArchivoEliminar']
    cotizacion_id = request.form['cotizacion_id2']
    print(nombreArchivoEliminar)
    print(cotizacion_id)
    
    try:
        documento = Document.query.filter_by(nombre=nombreArchivoEliminar, cotizacion_id=cotizacion_id).first()
        if documento:
            # Extraer el public_id de la URL
            public_id = extract_public_id(documento.url)
            if public_id:
                # Eliminar el archivo de Cloudinary
                cloudinary.uploader.destroy(public_id)

            # Eliminar el registro de la base de datos
            db.session.delete(documento)
            db.session.commit()
            
            flash('Archivo eliminado exitosamente', 'success')
        else:
            flash('El archivo a eliminar no existe', 'error')
    except Exception as e:
        flash(f'Error al eliminar el archivo: {str(e)}', 'error')
    
    return redirect(url_for('listar_documentos', cotizacionid=documento.cotizacion_id))



@app.route('/documentos/<int:cotizacionid>')
@requiere_login
def listar_documentos(cotizacionid):

    cotizacion = Cotizacion.query.get_or_404(cotizacionid)
    # Filtra los documentos por proyecto en la base de datos
    documentos = Document.query.filter_by(cotizacion_id=cotizacionid).all()

    # Renderiza la plantilla enviando solo los documentos filtrados
    return render_template('documentos.html', documentos=documentos, cotizacion=cotizacion)


@app.route('/documentos', methods=["GET",'POST'])
@requiere_login
def mostrar_documentos():
    # Recupera todos los documentos de la base de datos
    documentos = Document.query.all()
    return render_template('documentos_proyecto.html', documentos=documentos)

@app.route('/upload', methods=['GET', 'POST'])
@requiere_login
def upload_file():
    if request.method == 'POST':
        if 'documento' not in request.files:
            return redirect(url_for('upload_file', error=True, mensaje="No se seleccionó ningún archivo"))
        
        archivo = request.files['documento']
        cotizacion_id = request.form.get('cotizacion')

        # Verificar si se seleccionó un archivo vacío
        if archivo.filename == '':
            return redirect(url_for('upload_file', error=True, mensaje="El archivo no es válido"))

        # Limitar tamaño del archivo (ejemplo: 2 MB)
        max_size = 2 * 1024 * 1024  # 2 MB
        if archivo.content_length > max_size:
            return redirect(url_for('upload_file', error=True, mensaje="El archivo es demasiado grande"))

        try:
            # Sube el archivo a Cloudinary
            result = cloudinary.uploader.upload(archivo, secure=True)
            
            # Guardar la URL en la base de datos
            nuevo_documento = Document(
                url=result['secure_url'],
                nombre=archivo.filename,
                fecha_subida=datetime.now(pytz.timezone('America/Bogota')).date(),
                cotizacion_id=cotizacion_id,
            )
            db.session.add(nuevo_documento)
            db.session.commit()

            return redirect(url_for('upload_file', success=True, cotizacionid=cotizacion_id))
        
        except Exception as e:
            db.session.rollback()
            return redirect(url_for('upload_file', error=True, mensaje=str(e)))

    # Renderizar la plantilla con las cotizaciones (en caso de GET)
    cotizaciones = Cotizacion.query.all()
    return render_template('subir_archivo.html', cotizaciones=cotizaciones)

@app.route('/subir_archivo', methods=["GET",'POST'])
@requiere_login
def subir_archivo():
    cotizaciones = Cotizacion.query.all()
    return render_template('subir_archivo.html', cotizaciones=cotizaciones)

@app.route("/soporte")
@requiere_login
def soporte():
    return render_template("soporte.html")

@app.route("/usuario_cotizacion", methods=["GET", "POST"])
@requiere_login
def userManager():
    clientes = Cliente.query.all()
    return render_template("usuario_cotizacion.html", clientes=clientes)

@app.route("/producto_servicio", methods=["GET", "POST"])
@requiere_login
def product_service():
    # Datos de cotización
    ciudad = request.form['ciudad']
    empresa = request.form['empresa_cliente_nombre']
    proyecto = request.form['nombre_proyecto']
    plazo = request.form['plazo_oferta']
    entrega = request.form['tiempo_entrega']
    anticipo = request.form['porcentaje_anticipo']
    p_acta = request.form['porcentaje_primera_acta']
    f_acta = request.form['porcentaje_acta_final']
    consecutivo = 1

    info=[ciudad,empresa, proyecto,plazo, entrega, anticipo, p_acta, f_acta, consecutivo]
    global infoz
    infoz=info
    productos = Producto.query.all()
    return render_template("producto_servicio.html", productos=productos)

@app.route("/crear_cotizacion", methods=['POST'])
@requiere_login
def cotizacion():
    tipo_usuario = request.form.get('tipo_usuario')
    cliente = None
    if tipo_usuario == 'registrado':
        cliente_id = request.form.get('cliente_existente')
        cliente = Cliente.query.get(cliente_id)
    elif tipo_usuario == 'nuevo':
        nombre_cliente = request.form.get('cliente_nombre')
        celular_cliente = request.form.get('cliente_celular')
        correo_cliente = request.form.get('cliente_correo')
        # Crear nuevo cliente
        cliente = Cliente(nombre=nombre_cliente, celular=celular_cliente, email=correo_cliente)
        db.session.add(cliente)
        db.session.commit()
    global clientez
    clientez = cliente
    return render_template("crear_cotizacion.html")


@app.route('/ver_cotizacion', methods=['POST'])
@requiere_login
def crear_cotizacion():
    # Datos del producto o servicio
    opcion = request.form.get('producto_servicio')
    global infoz
    info = infoz
    global clientez
    cliente = clientez

    ciudad = info[0]
    empresa = info[1]
    proyecto = info[2]
    plazo = info[3]
    entrega = info[4]
    anticipo = info[5]
    p_acta = info[6]
    f_acta = info[7]
    consecutivo = info[8]

    if opcion == 'producto':
        # Captura el valor del select de productos
        cotizacion = Cotizacion(ciudad=ciudad, empresa=empresa, proyecto=proyecto, plazo=plazo, entrega=entrega,anticipo=anticipo, p_acta=p_acta, f_acta=f_acta, consecutivo=consecutivo, cliente=cliente)
        db.session.add(cotizacion)
        db.session.commit()

        # Obtener los productos seleccionados
        for producto in Producto.query.all():
            if request.form.get(f'cantidad{producto.id}'):
                cantidad = int(request.form.get(f'cantidad{producto.id}'))
                tamano = request.form.get(f'tamano{producto.id}')
                if tamano == 'CUNETE':
                    tamano = 4
                elif tamano == 'GALON':
                    tamano = 20
                elif tamano == 'TAMBOR':
                    tamano = 200
                detalle = CotizacionProducto(cotizacion_id=cotizacion.id, producto_id=producto.id, cantidad=int(cantidad), tamano=tamano)
                db.session.add(detalle)
        db.session.commit()

    elif opcion == 'servicio':
        # Captura el valor del campo de texto para servicios
        servicio_ingresado = request.form.get('servicio')
        cotizacion = Cotizacion(ciudad=ciudad, empresa=empresa, proyecto=proyecto, plazo=plazo, entrega=entrega, anticipo=anticipo,p_acta=p_acta, f_acta=f_acta, consecutivo=consecutivo, cliente=cliente, servicio=servicio_ingresado)
        db.session.add(cotizacion)
        db.session.commit()

    return render_template('cotizacion_final.html', cotizacion=cotizacion)


@app.route('/lista_cotizaciones')
@requiere_login
def listar_cotizaciones():
    # Obtener las cotizaciones que no tienen versiones hijas
    cotizaciones_sin_hijas = db.session.query(Cotizacion).filter(
        ~Cotizacion.versiones.any()
    ).all()

    return render_template('lista_cotizaciones.html', cotizaciones=cotizaciones_sin_hijas)

@app.route('/versiones_cotizacion/<int:id>')
@requiere_login
def listar_versiones(id):
    cotizacion = Cotizacion.query.get_or_404(id)
    # Obtener todas las versiones de esta cotización, ordenadas por consecutivo descendente
    versiones = Cotizacion.query.filter_by(version_padre_id=cotizacion.id).order_by(Cotizacion.consecutivo.desc()).all()
    # Obtener la cotización actual y todas las versiones padres (incluyendo abuelo si existe)
    padres = []
    padre = cotizacion.version_padre
    while padre:
        padres.append(padre)
        padre = padre.version_padre
    padres.reverse()  # Para mostrar desde el más antiguo al más reciente

    return render_template('versiones_cotizacion.html', cotizacion=cotizacion, versiones=versiones, padres=padres)


@app.route('/cotizacion/<int:id>')
@requiere_login
def ver_cotizacion(id):
    cotizacion = Cotizacion.query.get_or_404(id)
    return render_template('ver_cotizacion.html', cotizacion=cotizacion)

@app.route('/cotizacion_modificacion/<int:id>', methods=['POST'])
@requiere_login
def modificar_cotizacion(id):
    cotizacion = Cotizacion.query.get_or_404(id)
    return render_template('modificar_cotizacion.html', cotizacion=cotizacion)

@app.route('/actualizar_cotizacion/<int:id>', methods=['POST'])
@requiere_login
def actualizar_cotizacion(id):
    # Obtener la cotización original
    cotizacion_padre = Cotizacion.query.get_or_404(id)
    
    # Crear la nueva cotización basada en la original, pero con los cambios
    nueva_cotizacion = Cotizacion(
        ciudad=request.form['ciudad'],
        empresa=request.form['empresa_cliente_nombre'],
        proyecto=request.form['nombre_proyecto'],
        plazo=request.form['plazo_oferta'],
        entrega=request.form['tiempo_entrega'],
        anticipo=request.form['porcentaje_anticipo'],
        p_acta=request.form['porcentaje_primera_acta'],
        f_acta=request.form['porcentaje_acta_final'],
        consecutivo=cotizacion_padre.consecutivo + 1,  # Aumentar el consecutivo
        cliente=cotizacion_padre.cliente,
        servicio=cotizacion_padre.servicio,
        version_padre_id=cotizacion_padre.id  # Establecer que es una versión de la anterior
    )
    
    # Guardar la nueva cotización en la base de datos para obtener un ID
    db.session.add(nueva_cotizacion)
    db.session.flush()  # Esto asigna un ID a nueva_cotizacion sin hacer commit todavía
    
    # Copiar los detalles de productos del padre a la nueva cotización
    for detalle in cotizacion_padre.productos_detalle:
        nuevo_detalle = CotizacionProducto(
            cotizacion_id=nueva_cotizacion.id,
            producto_id=detalle.producto_id,
            cantidad=detalle.cantidad,
            tamano=detalle.tamano
        )
        db.session.add(nuevo_detalle)
    
    # Guardar todos los cambios en la base de datos
    db.session.commit()
    
    # Redirigir a la vista de la nueva cotización
    return redirect(url_for('ver_cotizacion', id=nueva_cotizacion.id))



@app.route('/lista_clientes')
@requiere_login
def listar_clientes():
    clientes = Cliente.query.all()
    return render_template('lista_clientes.html', clientes=clientes)

@app.route("/añadir_cliente", methods=["GET", "POST"])
def clienteManager():
    if request.method == "POST":
        # Capturar los datos del formulario
        nombre_cliente = request.form.get("nombre")
        celular_cliente = request.form.get("celular")
        correo_cliente = request.form.get("correo")

        # Validar que los campos no estén vacíos
        if not nombre_cliente or not celular_cliente or not correo_cliente:
            flash("Todos los campos son obligatorios", "error")
            return redirect(url_for("clienteManager"))

        try:
            # Crear un nuevo cliente
            nuevo_cliente = Cliente(nombre=nombre_cliente, celular=celular_cliente, email=correo_cliente)

            # Añadirlo a la base de datos
            db.session.add(nuevo_cliente)
            db.session.commit()

            flash("Cliente añadido exitosamente", "success")
            return redirect(url_for("listar_clientes"))

        except Exception as e:
            # En caso de error, mostrar un mensaje
            flash(f"Error al añadir el cliente: {str(e)}", "error")
            db.session.rollback()

    # Si el método es GET, mostrar el formulario
    return render_template("añadir_cliente.html")

# Ruta para listar clientes y mostrar el formulario de edición
@app.route('/editar_cliente', methods=['GET', 'POST'])
@requiere_login
def editar_cliente():
    if request.method == 'POST':
        # Obtener los datos del formulario
        cliente_id = request.form.get('cliente')
        nuevo_numero = request.form.get('nuevo_numero')
        nuevo_correo = request.form.get('nuevo_correo')

        # Buscar el cliente en la base de datos
        cliente = Cliente.query.get(cliente_id)

        if cliente:
            # Actualizar los datos del cliente
            cliente.celular = nuevo_numero
            cliente.email = nuevo_correo
            db.session.commit()
            flash('Cliente actualizado con éxito')
        else:
            flash('Cliente no encontrado')

        return redirect(url_for('listar_clientes'))

    # Obtener la lista de clientes para mostrar en el formulario
    clientes = Cliente.query.all()
    return render_template('editar_cliente.html', clientes=clientes)





# Metodo para probar generación de cotización
"""
@app.route('/cotizacion_final', methods=['POST'])
def listar_cotizacion():
    # Obtener la cuarta cotización de la base de datos
    cotizacion = Cotizacion.query.offset(3).first()
    return render_template('cotizacion_final.html', cotizacion=cotizacion)
"""

if __name__ == "__main__":
    app.run(debug=True)
