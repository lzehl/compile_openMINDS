#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 19 11:22:51 2020

@author: zehl
"""
import copy
import json
import collections
import jsonschema.validators

class JSValidator(dict):
    def __init__(self, *args, **kwargs):
        # we overload setattr so set this manually
        kwargs = dict(
                (k.replace("@", "at_"), v) if "@" in k else (k, v) 
                for k, v in kwargs.items())
        d = dict(*args, **kwargs)
        
        dict.__init__(self, d)

#    def __setitem__(self, key, value):
#        dict.__setitem__(self, key, value)

#    def __delitem__(self, key):
#        dict.__delitem__(self, key)

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

#    def __delattr__(self, key):
#        self.__delitem__(key)
        
class CollectionGenerator(JSValidator):
    """
    Class for generating an openMINDS conform metadata collection.
    
    The CollectionGenerator class dynamically reads the openMINDS schemas of a 
    given version for generating, validating, and storing corresponding json-LD 
    metadata files in an openMINDS conform metadata collection. 
        
    Attributes
    ----------
    version2use : str
        Used version of openMINDS schemas.
    store2 : str
        Absolute file path to where the openMINDS metadata collection is going 
        to be stored. 
        
    Methods
    -------
    """
    _method_docstring_temp = " ".join(
            ["Generates", "a", "dictionary", "that", "is", "conform", "with", 
             "\nthe", "openMINDS", "({version2use})", "schema", "{sn}.", 
             "\n\nParameters\n----------", "\n    DYNAMINCALLY-BUILT", 
             "\n\nReturns\n-------", "\n    Dictionary", "conform", "with", 
             "the", "openMINDS", "\n    ({version2use})", "schema", "{sn}."])
    _orig_jschema = {}
    def __init__(self, version2use):
        """
        Parameters
        ----------
        version2use : str
            Version of openMINDS schemas that should be used. Available versions
            are "v1.0", "v2.0", or "v3.0".
        """
        self.openminds_version = version2use
        
        # define relative path to openMINDS version
        rpv = './%s' % version2use
        
        # open definitions.json to find out what schemas are available
        with open(rpv + '/definitions.json', 'r') as fp:
            definitions = json.load(fp)
        fp.close()
        
        # get names of all schemas within the definition.json file
#        schema_names = list(definitions['definitions'].keys())
        schema_names = list(definitions.keys())

        # create class attributes for all available schemas
        self.schemas = collections.namedtuple('schemas', schema_names)
        # transpose schema attributes to schema subclasses
        method_desc = ""
        for sn in schema_names:
            # define relative path to openMINDS schema
#            rp2s = '/'.join([rpv, 
#                             definitions['definitions'][sn]['$id'].replace(
#                                     '#', '') + '.schema.json'])
            rp2s = '/'.join([rpv, 
                             definitions[sn]['$id'].replace(
                                     '#', '') + '.schema.json'])                    
            # open openMINDS json-schema to find out it's properties
            with open(rp2s, 'r') as fp:
                jschema = json.load(fp)
            fp.close()
            
            self._orig_jschema[sn] = copy.deepcopy(jschema)

            # create method from schema using warlock
#            setattr(self.schemas, sn, warlock.model_factory(jschema, name=sn))
            setattr(self.schemas, sn, self.__ingest_jschema(jschema))
            # create dynamic docstring for each schema method
            method_params = ""
            for p, d in jschema['properties'].items():
                method_params += " ".join(
                        ["\n   ", p, ":", d['type']])
                for k, v in d.items():
                    if k == 'type':
                        continue
                    elif k == 'items':
                        method_params += " ".join(
                                ["\n\texpects -", str(v)])
                    else:
                        method_params += " ".join(
                                ["\n       ", k, "-", str(v)])
            temp_docstr = self._method_docstring_temp.format(
                    version2use=version2use, sn=sn)
            
            # update method docstring
            sm = getattr(self.schemas, sn)
            sm.__doc__ = temp_docstr.replace(
                    "\n    DYNAMINCALLY-BUILT", method_params)
                
            # collect method description
            method_desc += "".join(["\n    ", sn, "(",
                    ", ".join(sorted(list(jschema['properties'].keys()))), ")"])
        
        # add schema methods summary to class docstring
        self.__doc__ += method_desc

    def __ingest_jschema(self, jschema):
        """
        Generates a subclass based on the provided JSON schema.
        
        Parameters
        ----------
        jschema : dict
            dict representing valid JSON schema
            
        Returns
        -------
            subclass based on provided JSON schema
        """    
        class JSchema(JSValidator):
            
            def __init__(self, *args, **kwargs):    
                self.__dict__["schema"] = jschema
                JSValidator.__init__(self, *args, **kwargs)
                self.__dict__["validator_instance"] = \
                        jsonschema.validators.validator_for(jschema)
    
        return JSchema
    
    def save_collection(self, metadata_collection, store2):
        """
        Stores metadata as a collection in an openMINDS conform repository.
        
        Parameters
        ----------
        metadata_collection : list of dict
            openMINDS conform metadata collection in form of a list of Python 
            dictionaries as generated by this class.
        store2 : str
            Absolute file path to where the openMINDS metadata collection should 
            be stored. 
        """
        

        
