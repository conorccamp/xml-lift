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
                element_class = XmlEntity(element, self.parent_class)
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
        self.element = xml_element
        self.name = xml_element.tag
        self.parent = parent_class
        self.values = []
        self.children = []
        self.promote_key = False
        self.add_to_parent()
        self._init_donor_key()

    def _init_donor_key(self):
        '''Inherit parent donor key'''
        if self.parent:
            self.donor_key = self.parent.donor_key
        else:
            self.donor_key = None
        self.donor = False

    def add_to_parent(self):
        '''Appends current class to the Parent.children list'''
        if self.parent:
            self.parent._add_child_class(self)

    def _add_child_class(self, child):
        self.children.append(child)
        self._ask_for_key(child)

    def _ask_for_key(self, child):
        '''Asks child to set the donor key if it's name matches the provided key'''
        if args.keys and child.name in args.keys:
            child.promote_key = True
            self.donor = True

    def add_value(self, xml_element):
        '''Adds element.text as a value if it is not an empty string'''
        if xml_element.text and xml_element.text.strip():
            self.values.append(xml_element.text)

    def _add_donor_key(self):
        '''Adds donor key to parent and siblings and outputs elements on the same level if they are waiting'''
        if self.promote_key:
            self.donor_key = {self.parent.name+'_'+self.name: self.values[0]}
            self.parent.donor_key = self.donor_key
            for sibling in self.parent.children: sibling.donor_key = self.donor_key
            # output values for sibling elements that were waiting on the donor key
            map(lambda sib: sib._output_values(), self.parent.children)

    def _donor_key_check(self):
        '''Check to see if we need to wait for the parent to add a donor key'''
        if args.keys:
            # if this is the class donating the key it doesn't need to wait for an update
            if self.donor:
                return True
            # if parent donor key has been added, update all values and return True
            elif self.donor_key:
                if self.entity_type == 'array' and self.values:
                    for val in self.values[0]: val.update(self.donor_key)
                else:
                    for val in self.values: val.update(self.donor_key)
                return True
            # otherwise we need to wait for the donor key
            else:
                return False
        # Always pass the test if no key option was received
        else:
            return True

    def _output_criteria_check(self):
        '''Criteria for when values should be output to the stream.'''
        if args.tags:
            # if the element name matches the split tags and the donor key check passes
            if self.name in args.tags and self._donor_key_check():
                return True
        # Default is for the top level element (this is inefficient).
        else:
            if self.parent is None:
                return True
        return False

    def _output_values(self):
        if self._output_criteria_check() == True and self.values:
            sys.stdout.write(json.dumps({self.name: self.values[0]})+'\n')
            self._reset_values()

    def _reset_values(self):
        self.values = []
        self.donor_key = None

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
            self._add_donor_key()
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
        # output values for this element if it meets the requirements
        self._output_values()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subparser_name", help="sub-command help")

    # parser for the 'parse' command
    full_parser = subparsers.add_parser('full',
            help="Converts the full XML document to JSON")
    full_parser.add_argument("-f", "--filepath", required=True,
            help="path to file to be processed")
    full_parser.add_argument("-c", "--csv", help="output as csv", action="store_true")

    # parser for the 'split' command
    split_parser = subparsers.add_parser('split',
            help="outputs stream of elements based on provided tags")
    split_parser.add_argument("-f", "--filepath", required=True,
            help="path to file to be processed")
    split_parser.add_argument("-t", "--tags", nargs="+", required=True,
            help="element tags that will be split and output separately.")
    split_parser.add_argument("-k", "--keys", nargs="+",
            help="Values that will be donated from parents and serve as foreign keys for split elements")
#    split_parser.add_argument("-c", "--csv", help="output as csv", action="store_true")

    args = parser.parse_args()
    
    if args.subparser_name == 'full':
        args.tags = None
        args.keys = None
    filepath = args.filepath
    parser = Parser(filepath)
    for event, element in parser.iterparser:
        parser.parse_xml(event, element)


#class DiscogsEntity(XmlEntity):
#    def __init__(self, xml_element, parent_class):
#        super(XmlEntity, self).__init__()
#        self.name = xml_element.tag
#        self.parent = parent_class
#        self.add_to_parent()
#        self.values = []
#        self.children = []
#
#    def _return_values(self):
#        if self.name in args.split:
#            return True
#        else:
#            return False








