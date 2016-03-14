import argparse
import sys
import json
import xml.etree.cElementTree as et

class Parser(object):
    def __init__(self, filepath):
        self.iterparser =  Parser.get_parser(filepath)
        self.entities = {}
        self.path = []  
        self.parent_class = None

    @staticmethod
    def get_parser(filepath):
        """takes a path for an xml file and returns an iterparse object with start and end events"""
        xmlfile = open(filepath)
        return  et.iterparse(xmlfile, events=('start', 'end'))

    @staticmethod
    def get_from_dict(datadict, maplist):
        return reduce(lambda d, k: d.get(k), maplist, datadict)

    @staticmethod
    def set_in_dict(datadict, maplist, value):
        Parser.get_from_dict(datadict, maplist[:-1])[maplist[-1]] = value

    def parse_xml(self, event, element):
        if event == 'start':
            self.path.append(element.tag)
            # get element metadata and class from the entity array
            element_meta = Parser.get_from_dict(self.entities, self.path)
            if element_meta:
                element_class = element_meta.get('class')
            # create the element metadata if this is the first time we've seen it
            else:
                element_meta = {}
                Parser.set_in_dict(self.entities, self.path, element_meta)
                element_class = None
            # create the element class if this is the first time we've seen it
            if not element_class:
                element_class = DiscogsEntity(element, self.parent_class)
                element_meta.update({'class':element_class})
            self.parent_class = element_class
        else:
            if self.path:
                del self.path[-1]
            if self.parent_class:
                # the element is now closed so it can now be processed
                # iterparse only fully parses element.text on end events
                self.parent_class.add_value(element)
                self.parent_class.terminate_element()
                # move the parent class up one level
                self.parent_class = self.parent_class.parent

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
        if args.split:
            if self.name in args.split:
                return True
        else:
            if self.parent is None:
                return True
        return False

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
            sys.stdout.write(json.dumps({self.name: self.values[0]})+'\n')
            self._reset_values()
            

class DiscogsEntity(XmlEntity):
    def __init__(self, xml_element, parent_class):
        super(XmlEntity, self).__init__()
        self.name = xml_element.tag
        self.parent = parent_class
        self.add_to_parent()
        self.values = []
        self.children = []

#    def _return_values(self):
#        if self.name in args.split:
#            return True
#        else:
#            return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filepath")
    parser.add_argument("-s", "--split", nargs="+", 
            help="element names that will be split and output separately.")
    args = parser.parse_args()
    
    filepath = args.filepath
    parser = Parser(filepath)
    for event, element in parser.iterparser:
        parser.parse_xml(event, element)










