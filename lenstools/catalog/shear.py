"""

.. module:: catalog
	:platform: Unix
	:synopsis: This module handles galaxy catalogs and their properties


.. moduleauthor:: Andrea Petri <apetri@phys.columbia.edu>


"""

import numpy as np
from scipy.ndimage.filters import gaussian_filter
import astropy.table as tbl
import astropy.units as u

try:
	import matplotlib.pyplot as plt
	from matplotlib import cm
	matplotlib = True
except ImportError:
	matplotlib = False

from .. import extern as ext
from ..image.shear import ShearMap

##########################################################
################Catalog class#############################
##########################################################

class Catalog(tbl.Table):

	"""
	Class handler of a galaxy catalogue, inherits all the functionality from the astropy.table.Table

	"""

	def __init__(self,*args,**kwargs):

		#Call parent constructor
		super(Catalog,self).__init__(*args,**kwargs)

		#Set spatial information
		self.setSpatialInfo()


	########################################################################################

	def setSpatialInfo(self,field_x="x",field_y="y",unit=u.deg):

		"""
		Sets the spatial information in the catalog

		:param field_x: name of the column that contains the x coordinates of the objects
		:type field_x: str.

		:param field_y: name of the column that contains the y coordinates of the objects
		:type field_y: str.

		:param unit: measure unit of the spatial coordinates
		:type unit: astropy.unit
		"""
		
		self._field_x = field_x
		self._field_y = field_y
		self._position_unit = unit


	########################################################################################

	
	def pixelize(self,map_size,npixel=256,field_quantity=None,origin=np.zeros(2)*u.deg,smooth=None,accumulate="average",callback=None,**kwargs):

		"""
		Constructs a two dimensional square pixelized map version of one of the scalar properties in the catalog by assigning its objects on a grid

		:param map_size: spatial size of the map
		:type map_size: quantity

		:param npixel: number of pixels on a side
		:type npixel: int.

		:param field_quantity: name of the catalog quantity to map; if None, 1 is assumed
		:type field_quantity: str.

		:param origin: two dimensional coordinates of the origin of the map
		:type origin: array with units

		:param smooth: if not None, the map is smoothed with a gaussian filter of scale smooth
		:type smooth: quantity

		:param accumulate: if "sum" field galaxies that fall in the same pixel have their field_quantity summed, if "average" the sum is divided by the number of galaxies that fall in the pixel
		:type accumulate: str.

		:param callback: user defined function that gets called on field_quantity
		:type callback: callable or None

		:param kwargs: the keyword arguments are passed to callback
		:type kwargs: dict.

		:returns: two dimensional scalar array with the pixelized field (pixels with no objects are treated as NaN)
		:rtype: array 

		"""

		#Safety check
		assert map_size.unit.physical_type==self._position_unit.physical_type
		assert len(origin)==2
		assert origin.unit.physical_type==self._position_unit.physical_type
		assert self._field_x in self.columns,"There is no {0} field in the catalog!".format(self._field_x)
		assert self._field_y in self.columns,"There is no {0} field in the catalog!".format(self._field_y)

		#Horizontal and vertical positions
		x = self.columns[self._field_x] - origin[0].to(self._position_unit).value
		y = self.columns[self._field_y] - origin[1].to(self._position_unit).value

		if field_quantity is not None:

			if type(field_quantity)==str:
				assert field_quantity in self.columns,"There is no {0} field in the catalog!".format(field_quantity)
				scalar = self.columns[field_quantity].astype(np.float)
			elif type(field_quantity)==np.ndarray:
				assert len(field_quantity)==len(self),"You should provide a scalar property for each record!!"
				scalar = field_quantity
			elif type(field_quantity) in [int,float]:
				scalar = np.empty(len(self),dtype=np.float)
				scalar.fill(field_quantity)
			else:
				raise TypeError("field_quantity format not recognized!")

		else:
			scalar = np.ones(len(self))

		#Make sure x,y,scalar have all the same length
		assert len(x)==len(y) and len(y)==len(scalar)

		#If user decides, call a function on scalar
		if callback is not None:
			scalar = callback(scalar,**kwargs)

		#Perform the pixelization
		scalar_map = np.zeros((npixel,npixel))
		scalar_map.fill(np.nan)
		ext._pixelize.grid2d(x,y,scalar,map_size.to(self._position_unit).value,scalar_map)

		#If pixel averaging is requested we need to compute the pixel hit count too
		if accumulate=="average":
			
			#Compute hits
			hits = np.zeros((npixel,npixel))
			hits.fill(np.nan)
			ext._pixelize.grid2d(x,y,np.ones(len(self)),map_size.to(self._position_unit).value,hits)

			#Average the scalar map
			scalar_map /= hits

		elif accumulate=="sum":
			pass

		else:
			raise NotImplementedError("pixel collection method {0} not implemented!")

		#Maybe smooth
		if smooth is not None:
			
			#Smoothing scale in pixel
			assert smooth.unit.physical_type==self._position_unit.physical_type
			smooth_in_pixel = (smooth * npixel / map_size).decompose().value

			#Replace NaN with zeros
			scalar_map[np.isnan(scalar_map)] = 0.0

			#Smooth
			scalar_map = gaussian_filter(scalar_map,sigma=smooth_in_pixel)

		#Return
		return scalar_map.T



	########################################################################################

	
	def visualize(self,map_size,npixel,field_quantity=None,origin=np.zeros(2)*u.deg,smooth=None,fig=None,ax=None,colorbar=False,cmap="jet",**kwargs):

		"""
		Visualize a two dimensional square pixelized map version of one of the scalar properties in the catalog by assigning its objects on a grid (the pixelization is performed using the pixelize routine)

		:param map_size: spatial size of the map
		:type map_size: quantity

		:param npixel: number of pixels on a side
		:type npixel: int.

		:param field_quantity: name of the catalog quantity to map; if None, 1 is assumed
		:type field_quantity: str.

		:param origin: two dimensional coordinates of the origin of the map
		:type origin: array with units

		:param smooth: if not None, the map is smoothed with a gaussian filter of scale smooth
		:type smooth: quantity

		:param kwargs: the additional keyword arguments are passed to pixelize 
		:type kwargs: dict.

		:returns: two dimensional scalar array with the pixelized field (pixels with no objects are treated as NaN)
		:rtype: array 

		"""

		if not matplotlib:
			raise ImportError("matplotlib is not installed, cannot visualize!")

		#Create figure
		if (fig is None) or (ax is None):
			
			self.fig,self.ax = plt.subplots()

		else:

			self.fig = fig
			self.ax = ax

		#Compute the pixelization
		scalar_map = self.pixelize(map_size,npixel,field_quantity,origin,smooth,**kwargs)

		#Plot 
		ax0 = self.ax.imshow(scalar_map.T,origin="lower",interpolation="nearest",extent=[origin[0].to(self._position_unit).value,(origin[0]+map_size).to(self._position_unit).value,origin[1].to(self._position_unit).value,(origin[1]+map_size).to(self._position_unit).value],cmap=getattr(cm,cmap))
		self.ax.set_xlabel(r"$x$({0})".format(self._position_unit.to_string()),fontsize=18)
		self.ax.set_ylabel(r"$y$({0})".format(self._position_unit.to_string()),fontsize=18)

		#Colorbar
		if colorbar:
			cbar = plt.colorbar(ax0,ax=self.ax)
			if (field_quantity is not None) and (type(field_quantity)==str):
				cbar.set_label(field_quantity,size=18)
			else:
				cbar.set_label(r"$n$",size=18)


	########################################################################################


	def savefig(self,filename):

		"""
		Saves the catalog visualization to an external file

		:param filename: name of the file on which to save the map
		:type filename: str.

		"""

		self.fig.savefig(filename)


	########################################################################################

	def write(self,filename,**kwargs):

		self.meta["NGAL"] = len(self)
		self.meta["AUNIT"] = self._position_unit.to_string()
		super(Catalog,self).write(filename,**kwargs)


##########################################################
################ShearCatalog class########################
##########################################################

class ShearCatalog(Catalog):

	"""
	Class handler of a galaxy shear catalog, inherits all the functionality from the Catalog class

	"""

	########################################################################################

	def toMap(self,map_size,npixel,smooth,**kwargs):

		"""
		Convert a shear catalog into a shear map

		:param map_size: spatial size of the map
		:type map_size: quantity

		:param npixel: number of pixels on a side
		:type npixel: int.

		:param smooth: if not None, the map is smoothed with a gaussian filter of scale smooth
		:type smooth: quantity

		:param kwargs: additonal keyword arguments are passed to pixelize
		:type kwargs: dict.

		:returns: shear map
		:rtype: ShearMap

		"""

		#Shear components
		s1 = self.pixelize(map_size,npixel,field_quantity="shear1",smooth=smooth,accumulate="average",**kwargs)
		s2 = self.pixelize(map_size,npixel,field_quantity="shear2",smooth=smooth,accumulate="average",**kwargs)

		#Convert into map
		return ShearMap(np.array([s1,s2]),map_size)

	########################################################################################

	def write(self,filename,**kwargs):

		self.meta["NGAL"] = len(self)
		super(Catalog,self).write(filename,**kwargs)


