import argparse
import sys
import json
import xml.etree.cElementTree as et

#file_path = '/Users/conor/discogs_analysis/data/discogs_20160301_artists.xml'
#file_path = '/Users/conor/discogs_analysis/data/artist_test50.xml'
file_path = '/Users/conor/discogs_analysis/data/artist_test2.xml'
#file_path = '/Users/conor/discogs_analysis/data/artist_test.xml'
entities = {}
output = []

def get_parser(filepath):
    """takes a path for an xml file and returns an iterparse object with start and end events"""
    xmlfile = open(filepath)
    return  et.iterparse(xmlfile, events=('start', 'end'))

def get_from_dict(datadict, maplist):
    return reduce(lambda d, k: d.get(k), maplist, datadict)

def set_in_dict(datadict, maplist, value):
    get_from_dict(datadict, maplist[:-1])[maplist[-1]] = value

class XmlEntity(object):
    def __init__(self, xml_element, parent_class):
        self.xml_element = xml_element
        self.name = xml_element.tag
        self.parent = parent_class
        self.add_to_parent()
        self.values = []
        self.children = []

    def add_to_parent(self):
        if self.parent:
            self.parent.children.append(self)

    def add_value(self, xml_element):
        '''Adds element.text as a value if it is not an empty string'''
        if xml_element.text and xml_element.text.strip():
            self.values.append(xml_element.text)

    def _reset_values(self):
        self.values = []

    def _return_values(self):
        '''Criteria for when values should be output to the stream.
           Default is for the top level element (this is inefficient).'''
        if self.parent:
            return False
        else:
            return True

    def _set_entity_type(self):
        if len(self.children) == 0:
            self.entity_type = 'pair'
        elif (len(self.children) == 1 or 
              True in map(lambda c: True if len(c.values) > 1 else False, self.children)):
            self.entity_type = 'array'
        else:
            self.entity_type = 'object'

    def terminate_element(self):
        #executes once we've hit an end event for the corresponding element
        self._set_entity_type()
        if self.entity_type == 'pair':
            # adds None to values list if the element has no text
            if len(self.values) == 0: self.values = [None]
            return
        elif self.entity_type == 'array':
            values = []
            for child in self.children:
                if len(child.values) == 0: child.values = [None]
                values.extend([{child.name: val} for val in child.values])
            self.values.append(values)
        else:
            values = {}
            for child in self.children:
                if len(child.values) > 1:
                    raise Exception("Encountered unexpected child values for element: {}".format(self.name))
                elif len(child.values) == 0:
                    child.values = [None]
                values[child.name] = child.values[0]
            self.values.append(values)

        # reset child values since we're done with this instance
        map(lambda child: child._reset_values(), self.children)

        if self._return_values():
#            output.append({self.name: self.values[0]})
            sys.stdout.write(json.dumps({self.name: self.values[0]})+'\n')
            self._reset_values()
            

def parse_xml(iterparser, path=[], parent_class=None):
    for event, element in iterparser:
        if event == 'start':
            path.append(element.tag)
            # get element metadata and class from the entity array
            element_meta = get_from_dict(entities, path)
            if element_meta:
                element_class = element_meta.get('class')
            # create the element metadata if this is the first time we've seen it
            else:
                element_meta = {}
                set_in_dict(entities, path, element_meta)
                element_class = None
            # create the element class if this is the first time we've seen it
            if not element_class:
                element_class = DiscogsEntity(element, parent_class)
                element_meta.update({'class':element_class})
            parse_xml(iterparser, path, element_class)
        else:
            if path:
                del path[-1]
            if parent_class:
		# the element is now closed so it can now be processed
                # iterparse only fully parses element.text on end events
                parent_class.add_value(element)
                parent_class.terminate_element()
		# move the parent class up one level
		parent_class = parent_class.parent

class DiscogsEntity(XmlEntity):
    def __init__(self, xml_element, parent_class):
        super(XmlEntity, self).__init__()
        self.name = xml_element.tag
        self.parent = parent_class
        self.add_to_parent()
        self.values = []
        self.children = []

    def _return_values(self):
        if self.name in ['artist']:
            return True
        else:
            return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filepath")
    args = parser.parse_args()
    
    filepath = args.filepath
    iterparser = get_parser(filepath)
    parse_xml(iterparser)
    print entities








