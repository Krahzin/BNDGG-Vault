"""Small embedded wordlist for passphrase generation (EFF-style short words).

Kept short on purpose: this is for readability, not for Diceware-grade entropy
at 4 words. 300+ words gives ~8.2 bits/word.
"""

WORDS = """
acid amber anchor apple apron archer arrow aspen atlas autumn
bacon badge bagel baker balmy bamboo banjo barn basil basket
beacon beam beard beaver bell belt birch biscuit bison blade
blanket bloom blue boat bolt bonus border bottle boulder box
brave bread brick bridge brisk brook brush bubble bucket buffalo
bugle bundle burrow butter button cabin cable cactus camel candle
canoe canvas canyon carbon cargo carpet carrot castle cedar cello
chalk charm cherry chess chief chili chimney cider cinema circle
citrus clam clay cliff cloak cloud clover coast cobalt cocoa coffee
comet compass copper coral cork corn cotton couch cougar crane
crater crayon cream creek crest cricket crimson crisp crow crown
crystal cube cumin cup curl cyclone daisy dance dapper dawn delta
denim desert desk dew diamond digit dime dingo dodge dolphin dome
donkey dove dragon drift drum dune dusk eagle earth echo eclipse
elbow elder elk ember emerald engine enjoy envoy epic equal
erase ether falcon fable fan farm feather fence fern ferry field
fig finch fire flag flame flask fleet flint flock flute foam
fog foil forest forge fork fossil fox frame frost fruit fudge
galaxy garden garlic gecko gem ghost giant ginger glacier glade
glass gleam globe glove glow gold goose gorge grape grass gravel
green grid grove guard guitar gulf gust harbor hawk hay hazel
heart hedge herb hero hill hive hollow honey hood horizon horse
hotel hound house hub hue iceberg igloo inch ink inlet iris
iron island ivory ivy jade jaguar jam jar jasper jelly jewel
jolly journey joy judge juice jumbo jungle juniper kayak kelp
kettle key kite kiwi knoll koala lace lagoon lake lamp lantern
larch lark laser latch leaf ledge lemon lens lily lime linen
lion lizard llama loaf lobby lotus lucky lumber lunar lynx
magnet mango maple marble march marsh mask meadow medal melon
mesa metal meteor mint mirror mist mole monarch moon moose moss
moth mound mountain mouse mud muffin mulberry music mustang nectar
needle nest nickel night noble north nova nugget oak oasis
ocean olive onyx opal orbit orchid osprey otter owl oxen oyster
paddle page palm panda pansy panther paper parcel peach pearl
pebble pecan pedal pelican pencil pepper petal piano pier pilot
pine pink pint pipe pistachio planet plank plum pond pony poplar
poppy porch prairie prism puffin pulse pumpkin puzzle quartz quay
quill quince rabbit radar raft rail rain raven reef relay
ribbon rice ridge rifle ring river road robin rocket rodeo
roof root rope rose rowan ruby rug runner rust saddle sage
sail salt sand satin scale scarf school scout sea seed sequoia
shade shell shore shrub silk silver skate sky slate sled slope
smoke snail snow soap solar sonnet spark sparrow spice spider
spiral spring spruce squash squid stable star steam steel stem
stone storm stream sugar summit sun swan swift sword syrup table
taco tail talon tangerine tapir teal tent terra thistle thorn
thyme tide tiger timber toad toast topaz torch trail tram tree
tribe trout truck tulip tundra tunnel turtle twig umber unicorn
valley vanilla vapor velvet vessel vine violet vivid walnut walrus
wand water wave wheat whale willow wind window wing wolf wren
yarrow yew yoga zebra zephyr zinc zone
""".split()


def word_count() -> int:
    return len(WORDS)
