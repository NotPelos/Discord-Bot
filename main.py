import discord
from discord.ext import commands
from discord import Interaction, SelectOption, app_commands
from discord.ui import View, Select, Button, Modal, TextInput
import json

# Cargar configuraciones
with open("parametros.json", "r", encoding="utf-8") as f:
    config = json.load(f)
with open("secrets.json", "r", encoding="utf-8") as e:
    secrets = json.load(e)

# Configurar bot e intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Variables globales
tipo_sanciones = config["tipoSanciones"]
tipo_bandas = config["Bandas"]
TOKEN = secrets["TOKEN"]
ID_Discord = secrets["ID_Servidor"]
CHANNEL_ID = 1215111764669112392  # ID del canal específico para registrar ventas
ChannelBand = 1215111764669112392


# Funciones de utilidad
def cargar_bandas():
    with open("parametros.json", "r", encoding="utf-8") as file:
        data = json.load(file)
        return data["Bandas"]


def actualizar_bandas(nombre_banda):
    with open("parametros.json", "r+", encoding="utf-8") as file:
        data = json.load(file)
        data["Bandas"].append({"name": nombre_banda, "value": nombre_banda})
        file.seek(0)
        json.dump(data, file, indent=4, ensure_ascii=False)
        file.truncate()


def es_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator

    return discord.app_commands.check(predicate)


# Clase para el menú de selección
class BandasSelect(Select):
    def __init__(self, bandas):
        options = [
            SelectOption(label=banda["name"], value=banda["value"]) for banda in bandas
        ]
        super().__init__(
            placeholder="Elige una banda...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: Interaction):
        role_name = self.values[0]
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"Rol '{role_name}' asignado correctamente.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Rol no encontrado.", ephemeral=True
            )


# Clase para la vista que contiene el Select
class BandasView(View):
    def __init__(self, bandas):
        super().__init__(timeout=None)
        self.add_item(BandasSelect(bandas))


# Clase para el formulario de ventas
class VentaModal(Modal):
    def __init__(self, title="Registrar Venta"):
        super().__init__(title=title)
        self.venta_para = TextInput(
            label="Venta para", placeholder="Nombre del comprador"
        )
        self.articulos = TextInput(
            label="Artículos",
            placeholder="Descripción del artículo 1\nDescripción del artículo 2\n...",
            style=discord.TextStyle.paragraph,
        )
        self.cantidades = TextInput(
            label="Cantidades",
            placeholder="Cantidad del artículo 1\nCantidad del artículo 2\n...",
            style=discord.TextStyle.paragraph,
        )
        self.precios = TextInput(
            label="Precios",
            placeholder="Precio del artículo 1\nPrecio del artículo 2\n...",
            style=discord.TextStyle.paragraph,
        )

        self.add_item(self.venta_para)
        self.add_item(self.articulos)
        self.add_item(self.cantidades)
        self.add_item(self.precios)

    async def on_submit(self, interaction: discord.Interaction):
        articulos = self.articulos.value.split("\n")
        cantidades = self.cantidades.value.split("\n")
        precios = self.precios.value.split("\n")

        articulos_vendidos = []
        total = 0.0

        for articulo, cantidad, precio in zip(articulos, cantidades, precios):
            cantidad = int(cantidad)
            precio = float(precio)
            subtotal = cantidad * precio
            total += subtotal
            articulos_vendidos.append(
                f"{articulo}: {cantidad} unidad(es) a ${precio:.2f} cada una"
            )

        articulos_vendidos_text = "\n".join(articulos_vendidos)

        user_roles = interaction.user.roles
        ventas_channel = None
        for role in user_roles:
            for channel in interaction.guild.text_channels:
                if (
                    "ventas" in channel.name
                    and channel.permissions_for(role).read_messages
                ):
                    ventas_channel = channel
                    break
            if ventas_channel:
                break

        if ventas_channel:
            embed = discord.Embed(
                title="Nueva Venta Registrada", color=discord.Colour.green()
            )
            embed.add_field(
                name="Venta para", value=self.venta_para.value, inline=False
            )
            embed.add_field(
                name="Articulos vendidos", value=articulos_vendidos_text, inline=False
            )
            embed.add_field(name="Total", value=f"${total:.2f}", inline=False)
            await ventas_channel.send(embed=embed)
            await interaction.response.send_message(
                "Venta registrada exitosamente.", ephemeral=True, delete_after=5
            )
        else:
            await interaction.response.send_message(
                "No se pudo encontrar el canal de ventas correspondiente.",
                ephemeral=True,
            )


# Clase para la vista del botón de registro de ventas
class VentaView(View):
    def __init__(self):
        super().__init__(timeout=None)
        registrar_button = Button(
            label="Registrar Venta", style=discord.ButtonStyle.primary
        )
        registrar_button.callback = self.registrar_venta
        self.add_item(registrar_button)

    async def registrar_venta(self, interaction: Interaction):
        await interaction.response.send_modal(VentaModal())


# Manejo de errores de comandos de aplicación
@bot.event
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
):
    if isinstance(error, discord.app_commands.errors.CheckFailure):
        if interaction.response.is_done():
            await interaction.followup.send(
                "No tienes permiso para ejecutar este comando.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "No tienes permiso para ejecutar este comando.", ephemeral=True
            )
    else:
        print(f"Un error ocurrió al ejecutar un comando: {error}")


# Evento on_ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    search_text = "Selecciona tu banda:"
    channel = bot.get_channel(ChannelBand)
    message_found = None

    async for message in channel.history(limit=100):
        if message.author == bot.user and search_text in message.content:
            message_found = message
            break

    if message_found:
        await message_found.delete()
        print("Mensaje antiguo encontrado y eliminado.")

    bandas = cargar_bandas()
    view = BandasView(bandas)
    await channel.send("Selecciona tu banda:", view=view)
    print("Nuevo mensaje con select box enviado.")

    # Enviar el mensaje con el botón para registrar ventas
    channel = bot.get_channel(CHANNEL_ID)
    message_text = "Pulsa en el botón para registrar tus ventas"
    async for message in channel.history(limit=100):
        if message.author == bot.user and message_text in message.content:
            await message.delete()

    ventas_view = VentaView()
    await channel.send(message_text, view=ventas_view)
    print("Mensaje con botón de registro de ventas enviado.")

    try:
        guild_id = ID_Discord
        guild = discord.Object(id=guild_id)
        await bot.tree.sync(guild=guild)
        print(f"Synced commands to guild ID {guild_id}")
    except Exception as e:
        print(e)


# Comando para crear bandas
@bot.tree.command(
    name="crearbanda",
    description="Crea una banda con el nombre y el color especificados.",
)
@app_commands.describe(
    nombre="Nombre de la banda", color_hex="Color en hexadecimal sin el #"
)
@es_admin()
async def crear_banda(interaction: discord.Interaction, nombre: str, color_hex: str):
    try:
        color = discord.Colour(int(color_hex.lstrip("#"), 16))
    except ValueError:
        await interaction.response.send_message(
            "El código de color proporcionado no es válido.",
            ephemeral=True,
            delete_after=5,
        )
        return

    categoria = await interaction.guild.create_category(name=nombre)
    rol = await interaction.guild.create_role(name=nombre, color=color)

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(
            read_messages=False
        ),
        rol: discord.PermissionOverwrite(read_messages=True),
    }

    await categoria.create_text_channel(name="lideres-staff", overwrites=overwrites)
    await categoria.create_text_channel(name="entradas-salidas", overwrites=overwrites)
    await categoria.create_text_channel(name="ventas", overwrites=overwrites)
    actualizar_bandas(nombre)
    await interaction.response.send_message(
        f'Se ha creado la banda "{nombre}" con éxito y se han establecido los permisos.',
        ephemeral=True,
        delete_after=5,
    )


# Comando para eliminar bandas
@bot.tree.command(
    name="eliminarbanda",
    description="Elimina una banda, el rol y expulsa a quienes tengan ese rol",
)
@app_commands.choices(
    banda=[
        app_commands.Choice(name=banda["name"], value=banda["value"])
        for banda in config["Bandas"]
    ]
)
@es_admin()
async def eliminar_banda(
    interaction: discord.Interaction, banda: app_commands.Choice[str]
):
    nombre = banda.value
    guild = interaction.guild
    categoria = discord.utils.get(interaction.guild.categories, name=nombre)
    rol = discord.utils.get(interaction.guild.roles, name=nombre)

    if categoria is None and rol is None:
        await interaction.response.send_message(
            f"No se encontró la banda o el rol con el nombre '{nombre}'.",
            ephemeral=True,
            delete_after=5,
        )
        return

    if rol is not None:
        for member in list(guild.members):
            if len(member.roles) == 2 and rol in member.roles:
                try:
                    await member.kick(reason=f"Eliminación de la banda {nombre}")
                except discord.Forbidden:
                    await interaction.followup.send(
                        f"No se pudo expulsar a {member.display_name} debido a la falta de permisos.",
                        ephemeral=True,
                    )
                except discord.HTTPException as e:
                    await interaction.followup.send(
                        f"No se pudo expulsar a {member.display_name} debido a un error HTTP: {e}",
                        ephemeral=True,
                    )

    if categoria is not None:
        for canal in categoria.channels:
            await canal.delete()
        await categoria.delete()

    if rol is not None:
        await rol.delete()

    config["Bandas"] = [banda for banda in config["Bandas"] if banda["value"] != nombre]
    with open("parametros.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

    try:
        with open("sanciones.json", "r+", encoding="utf-8") as file:
            sanciones = json.load(file)
            if nombre in sanciones:
                del sanciones[nombre]
                file.seek(0)
                json.dump(sanciones, file, indent=4, ensure_ascii=False)
                file.truncate()
    except FileNotFoundError:
        print("El archivo sanciones.json no fue encontrado.")
    except Exception as e:
        print(f"Error al actualizar sanciones.json: {e}")

    await interaction.response.send_message(
        f"Se ha eliminado la banda y rol '{nombre}' con éxito.",
        ephemeral=True,
        delete_after=5,
    )


# Comando de anuncio
@bot.tree.command(
    name="anuncio",
    description="Lanza un comunicado en el canal de comunicados mencionando a todos, utilizar \n para saltos de linea",
)
@es_admin()
async def anuncio(interaction: discord.Interaction, *, titulo: str, contenido: str):
    comunicados_channel = discord.utils.get(
        interaction.guild.text_channels, name="comunicados"
    )

    if not comunicados_channel:
        await interaction.response.send_message(
            "El canal 'comunicados' no se encuentra en el servidor.",
            ephemeral=True,
            delete_after=5,
        )
        return

    contenido_formateado = contenido.replace("\\n", "\n")
    embed = discord.Embed(
        title=titulo, description=contenido_formateado, color=discord.Colour.blue()
    )
    embed.set_footer(text="Grupo Oasis | Ilícito")

    try:
        await comunicados_channel.send(
            content="@everyone",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        await interaction.response.send_message(
            "El anuncio ha sido publicado en 'comunicados'.",
            ephemeral=True,
            delete_after=5,
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "No tengo permisos para enviar mensajes en 'comunicados'.",
            ephemeral=True,
            delete_after=5,
        )
    except discord.HTTPException as e:
        await interaction.response.send_message(
            f"Ocurrió un error al enviar el mensaje: {e}",
            ephemeral=True,
            delete_after=5,
        )


# Autocompletar para bandas
async def autocompletar_bandas(interaction: discord.Interaction, current: str):
    roles = await interaction.guild.fetch_roles()
    return [
        app_commands.Choice(name=role.name, value=role.name)
        for role in roles
        if current.lower() in role.name.lower()
    ][:25]


# Comando para asignar banda
@bot.tree.command(
    name="darbanda", description="Asigna un usuario a un rol existente en el servidor."
)
@es_admin()
@app_commands.autocomplete(banda=autocompletar_bandas)
async def dar_banda(
    interaction: discord.Interaction, usuario: discord.User, banda: str
):
    rol = discord.utils.get(interaction.guild.roles, name=banda)
    if rol is None:
        await interaction.response.send_message(
            f"No se encontró el rol '{banda}'.", ephemeral=True
        )
        return

    member = interaction.guild.get_member(usuario.id)
    if member is None:
        await interaction.response.send_message(
            "No se encontró al usuario en el servidor.", ephemeral=True
        )
        return

    await member.add_roles(rol)
    await interaction.response.send_message(
        f"El rol '{rol.name}' ha sido asignado al usuario {usuario.display_name}.",
        ephemeral=True,
    )


# Comando para sancionar
@bot.tree.command(
    name="sancion", description="Comando para comunicar una sancion a un usuario."
)
@es_admin()
@app_commands.describe(
    tipo="Elige entre Aviso, Falta o Disband.",
    banda="Nombre de las bandas de la lista",
    motivo="Detalles de la sanción.",
)
@app_commands.choices(
    tipo=[
        app_commands.Choice(name=opcion["name"], value=opcion["value"])
        for opcion in tipo_sanciones
    ],
    banda=[
        app_commands.Choice(name=bandas["name"], value=bandas["value"])
        for bandas in tipo_bandas
    ],
)
async def sancion(interaction: discord.Interaction, tipo: str, banda: str, motivo: str):
    colores = {
        "Aviso": discord.Colour.orange(),
        "Falta": discord.Colour.red(),
        "Disband": discord.Colour(0x000000),
    }
    color_embed = colores[tipo]
    embed = discord.Embed(
        title="**Sanción**",
        description=f"La banda {banda} ha recibido un/a **{tipo}** por: {motivo}",
        color=color_embed,
    )
    embed.set_footer(text="Grupo Oasis | Ilícito")

    sanciones_channel = discord.utils.get(
        interaction.guild.text_channels, name="sanciones"
    )
    if sanciones_channel is None:
        await interaction.response.send_message(
            "El canal 'sanciones' no existe.", ephemeral=True, delete_after=5
        )
        return

    if tipo != "Disband":
        with open("sanciones.json", "r+", encoding="utf-8") as file:
            sanciones = json.load(file)
            if banda not in sanciones:
                sanciones[banda] = {"Aviso": 0, "Falta": 0}
            if tipo in sanciones[banda]:
                sanciones[banda][tipo] += 1
            file.seek(0)
            json.dump(sanciones, file, indent=4, ensure_ascii=False)
            file.truncate()

    await sanciones_channel.send(embed=embed)
    await interaction.response.send_message(
        f"La sanción ha sido publicada en el canal 'sanciones'.",
        ephemeral=True,
        delete_after=5,
    )


# Comando para mostrar el contador de sanciones
@bot.tree.command(
    name="contadorsancion",
    description="Muestra el contador de sanciones para una banda específica.",
)
@app_commands.describe(banda="Nombre de la banda para ver su contador de sanciones.")
@app_commands.choices(
    banda=[
        app_commands.Choice(name=bandas["name"], value=bandas["value"])
        for bandas in tipo_bandas
    ]
)
async def contador_sancion(interaction: discord.Interaction, banda: str):
    with open("sanciones.json", "r", encoding="utf-8") as file:
        sanciones = json.load(file)

    if banda in sanciones:
        msg = f"Sanciones para {banda}: \n"
        for tipo, cantidad in sanciones[banda].items():
            msg += f"{tipo}: {cantidad}\n"
    else:
        msg = "Esta banda no tiene sanciones registradas."

    await interaction.response.send_message(msg, ephemeral=True)


# Inicia el bot con el token proporcionado
bot.run(TOKEN)
