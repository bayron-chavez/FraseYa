CREATE TABLE IF NOT EXISTS CATALOGO (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL CHECK(length(trim(nombre)) > 0),
    version INTEGER NOT NULL DEFAULT 0 CHECK(version >= 0),
    fecha_publicacion TEXT,
    autor TEXT NOT NULL DEFAULT '',
    origen TEXT NOT NULL CHECK(origen IN ('propia', 'compartida'))
);
CREATE TABLE IF NOT EXISTS CATEGORIA (
    id INTEGER PRIMARY KEY,
    catalogo_id INTEGER NOT NULL REFERENCES CATALOGO(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL CHECK(length(trim(nombre)) > 0),
    color TEXT NOT NULL DEFAULT '#64748B'
        CHECK(length(color) = 7 AND substr(color,1,1) = '#'
              AND substr(color,2) NOT GLOB '*[^0-9A-Fa-f]*'),
    UNIQUE(catalogo_id, nombre)
);
CREATE TABLE IF NOT EXISTS FRASE (
    id INTEGER PRIMARY KEY,
    categoria_id INTEGER NOT NULL REFERENCES CATEGORIA(id) ON DELETE RESTRICT,
    titulo TEXT NOT NULL CHECK(length(trim(titulo)) > 0),
    abreviatura TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(abreviatura)) > 0),
    contenido TEXT NOT NULL CHECK(length(trim(contenido)) > 0),
    origen TEXT NOT NULL CHECK(origen IN ('propia', 'compartida')),
    actualizado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS VARIABLE (
    id INTEGER PRIMARY KEY,
    frase_id INTEGER NOT NULL REFERENCES FRASE(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL CHECK(length(trim(nombre)) > 0),
    orden INTEGER NOT NULL CHECK(orden >= 0),
    UNIQUE(frase_id, nombre),
    UNIQUE(frase_id, orden)
);
CREATE TABLE IF NOT EXISTS SINCRONIZACION (
    id INTEGER PRIMARY KEY,
    fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version_aplicada INTEGER CHECK(version_aplicada >= 0),
    estado TEXT NOT NULL CHECK(estado IN ('actualizada','sin_cambios','error')),
    detalle TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS CONFIGURACION (
    clave TEXT PRIMARY KEY CHECK(length(trim(clave)) > 0),
    valor TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_frase_categoria ON FRASE(categoria_id);
CREATE INDEX IF NOT EXISTS idx_frase_origen ON FRASE(origen);
CREATE TRIGGER IF NOT EXISTS frase_origen_insert
BEFORE INSERT ON FRASE
WHEN NEW.origen != (SELECT ca.origen FROM CATEGORIA c JOIN CATALOGO ca
                   ON ca.id=c.catalogo_id WHERE c.id=NEW.categoria_id)
BEGIN SELECT RAISE(ABORT, 'El origen de la frase no coincide con su catálogo'); END;
CREATE TRIGGER IF NOT EXISTS frase_origen_update
BEFORE UPDATE OF origen, categoria_id ON FRASE
WHEN NEW.origen != (SELECT ca.origen FROM CATEGORIA c JOIN CATALOGO ca
                   ON ca.id=c.catalogo_id WHERE c.id=NEW.categoria_id)
BEGIN SELECT RAISE(ABORT, 'El origen de la frase no coincide con su catálogo'); END;
CREATE TRIGGER IF NOT EXISTS categoria_catalogo_update
BEFORE UPDATE OF catalogo_id ON CATEGORIA
WHEN EXISTS(SELECT 1 FROM FRASE f JOIN CATALOGO ca ON ca.id=NEW.catalogo_id
            WHERE f.categoria_id=OLD.id AND f.origen != ca.origen)
BEGIN SELECT RAISE(ABORT, 'La categoría contiene frases de otro origen'); END;
CREATE TRIGGER IF NOT EXISTS catalogo_origen_update
BEFORE UPDATE OF origen ON CATALOGO
WHEN EXISTS(SELECT 1 FROM FRASE f JOIN CATEGORIA c ON c.id=f.categoria_id
            WHERE c.catalogo_id=OLD.id AND f.origen != NEW.origen)
BEGIN SELECT RAISE(ABORT, 'El catálogo contiene frases de otro origen'); END;
