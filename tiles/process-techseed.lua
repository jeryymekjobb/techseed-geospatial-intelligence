-- tilemaker's OpenMapTiles processing (resources/process-openmaptiles.lua in the tilemaker image,
-- based on the OpenMapTiles schema, © KlokanTech.com & OpenMapTiles contributors, CC BY 4.0) with two
-- changes for the demo's offline map, which shows a whole scenario area at zoom 9-11:
--
-- * Every railway without a service tag is kept from zoom 8, as the main lines are. The original
--   keeps lines without usage=main only from zoom 10, which tileserver-gl, rendering 256 px images
--   from the zoom below, shows only from zoom 11 (Ådalsbanan north of Kramfors was missing).
-- * Road numbers (ref) are written to transportation_name from zoom 9, so the style can label the
--   larger roads at the demo's scale; the original writes primary roads from 10 and secondary
--   from 11.
--
-- tools/build_offline_tiles.py runs it with tilemaker's own config-openmaptiles.json.

dofile("resources/process-openmaptiles.lua")

RAILWAY_MINZOOM = 8
ROAD_REF_MINZOOM = 9

local openmaptiles_write_to_transportation_layer = write_to_transportation_layer
function write_to_transportation_layer(minzoom, highway_class, subclass, ramp, service, is_rail, is_road, is_area)
	if is_rail and subclass == "rail" and (service == nil or service == "") then
		minzoom = math.min(minzoom, RAILWAY_MINZOOM)
	end
	return openmaptiles_write_to_transportation_layer(minzoom, highway_class, subclass, ramp, service, is_rail, is_road, is_area)
end

local current_layer = nil
local openmaptiles_Layer = Layer
local openmaptiles_MinZoom = MinZoom
function Layer(name, is_area)
	current_layer = name
	return openmaptiles_Layer(name, is_area)
end
function MinZoom(zoom)
	if current_layer == "transportation_name" and Find("highway") ~= "" and Holds("ref") then
		zoom = math.min(zoom, ROAD_REF_MINZOOM)
	end
	return openmaptiles_MinZoom(zoom)
end
