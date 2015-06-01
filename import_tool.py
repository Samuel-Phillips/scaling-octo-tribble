import tempfile
import traceback
import shutil
import os.path
import os
from zipfile import ZipFile
from contextlib import contextmanager
import shapefile
import pginterface
import pyproj

@contextmanager
def tempdir():
    """Contect manager for a temporary directory. Directory is deleted
    when the context manager exits."""
    the_dir = tempfile.mkdtemp()
    try:
        yield the_dir
    finally:
        shutil.rmtree(the_dir)

def import_shape_file(saveable, db, proj):
    """Imports a zipped shapefile (form the saveable parameter, which must
    have a .save method) into the pginterface.Rooftops object db. Raises
    import_tool.error with messages relating to the error encountered.
    proj is temporary parameter inputted from an HTML form until this whole
    projections situation is sorted out."""
    with tempdir() as root:
        zip_name = os.path.join(root, "map.zip")
        sf_dir = os.path.join(root, "shapes")

        saveable.save(zip_name)
        try:
            ZipFile(zip_name, mode='r').extractall(path=sf_dir)
        except:
            raise error("Error while opening the uploaded file. Make sure it is in zip format.")
        sf_names = set(name[:-4] for name in os.listdir(sf_dir)
                if name.endswith('.shp') or name.endswith('.shx')
                or name.endswith('.dbf'))
        if len(sf_names) == 0:
            raise error("No shapefile found in zip. The zip must contain exactly one shapefile, and it must not be in a subdirectory.")
        elif len(sf_names) == 1:
            name = sf_names.pop()
            joined = os.path.join(sf_dir, name)
            for ext in 'shp dbf'.split(): # add prj here when #1 fixed
                if not os.path.isfile(joined + '.' + ext):
                    return error('.' + ext + ' file missing from zip! Please include the entire shapefile.')
            try:
                sf = shapefile.Reader(joined)
                perform_import(sf, proj, db)
            except shapefile.ShapefileException:
                raise error("Invalid shapefile")
        else:
            raise error("Found multiple shapefiles with names {}. Only one shapefile may be present in the zip.".format(
                        ', '.join(sf_names)))

def perform_import(sf, proj, db):
    """Takes a pyshp instance and imports its point to the database."""
    cols = {n: None for n in 'kwhs BuidArea Perc System Savings UseRoof Zone'.split()}
    for i, f in enumerate(sf.fields):
        if f[0] in cols:
            cols[f[0]] = i - 1
    try:
        db.add_rects(
            pginterface.Rect(
                wktshape=points2wkt(row.shape.points, proj),
                building_area=row.record[cols['BuidArea']],
                useable_build_area=row.record[cols['UseRoof']],
                percent_usable=row.record[cols['Perc']],
                kwhs=row.record[cols['kwhs']],
                system_size_kw=row.record[cols['System']],
                savings=int(100 * float(row.record[cols['Savings']]))
            ) for row in sf.shapeRecords() if is_useful(row)
        )
    except:
        traceback.print_exc()
        raise error("Database error, see log")

def points2wkt(points, proj):
    """Converts a list of points into a WKT polygon."""
    points.append(points[0]) # work around for polygons not being connected
    outproj = pyproj.Proj('+proj=merc +lon_0=0 +k=1 +x_0=0 +y_0=0 +a=6378137 +b=6378137 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs')
    inproj = pyproj.Proj(proj)
    
    return "POLYGON(({}))".format(
            ','.join(
                ' '.join(str(test(dim, point)) for dim in pyproj.transform(
                    inproj, outproj, *point)[:2]
                ) for point in points
            ))

def is_useful(row):
    return True

def test(dim, point):
    if str(dim) == 'inf':
        print("Shit, let's be {}".format(repr(point)))
    return dim

class error(Exception):
    """Generic error from the import process that contains a human readable
    error string."""
    pass
