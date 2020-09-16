#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 19 11:22:51 2020

@author: zehl
"""
import collections
import copy
import json
import jsonpatch
import jsonschema
from jsonschema.validators import validator_for
import urllib
import warnings

class InvalidOperation(RuntimeError):
    pass

class ValidationError(ValueError):
    pass

class baseJSchema(dict):
    def __init__(self, *args, **kwargs):
        # we overload setattr so set this manually
        d = dict(*args, **kwargs)

        try:
            self.validate(d)
        except ValidationError as exc:
            raise ValueError(str(exc))
        else:
            dict.__init__(self, d)

        self.__dict__["__original__"] = copy.deepcopy(d)

    def __setitem__(self, key, value):
        mutation = dict(self.items())
        mutation[key] = value
        try:
            self.validate(mutation)
        except ValidationError as exc:
            msg = "Unable to set '%s' to %r. Reason: %s" % (key, value, str(exc))
            raise InvalidOperation(msg)

        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        mutation = dict(self.items())
        del mutation[key]
        try:
            self.validate(mutation)
        except ValidationError as exc:
            msg = "Unable to delete attribute '%s'. Reason: %s" % (key, str(exc))
            raise InvalidOperation(msg)

        dict.__delitem__(self, key)

    def __getattr__(self, key):
        print(key)
        try:
            return self.__getitem__(key)
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __delattr__(self, key):
        self.__delitem__(key)

    # BEGIN dict compatibility methods

    def clear(self):
        raise InvalidOperation()

    def pop(self, key, default=None):
        raise InvalidOperation()

    def popitem(self):
        raise InvalidOperation()

    def copy(self):
        return copy.deepcopy(dict(self))

    def __copy__(self):
        return self.copy()

    def __deepcopy__(self, memo):
        return copy.deepcopy(dict(self), memo)

    def update(self, other):
        mutation = dict(self.items())
        mutation.update(other)
        try:
            self.validate(mutation)
        except ValidationError as exc:
            raise InvalidOperation(str(exc))
        dict.update(self, other)

    def items(self):
        return copy.deepcopy(dict(self)).items()

    def values(self):
        return copy.deepcopy(dict(self)).values()

    # END dict compatibility methods

    @property
    def patch(self):
        """Return a jsonpatch object representing the delta"""
        original = self.__dict__["__original__"]
        return jsonpatch.make_patch(original, dict(self)).to_string()

    def validate(self, obj):
        """Apply a JSON schema to an object"""
        try:
            self.validator_instance.validate(obj)

        except jsonschema.ValidationError as exc:
            raise ValidationError(str(exc))
            
            
class CompileOpenMINDS():
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
    
    def __init__(self, schemamodel, version2use):
        """
        Parameters
        ----------
        version2use : str
            Version of openMINDS schemas that should be used. Available versions
            are "v1.0", "v2.0", or "v3.0".
        """
        self.openminds_version = version2use
        self.schema_model = schemamodel
        
        # define URL to stated openMINDS version
        schemaorigin = "/".join([
                "https:/", "raw.githubusercontent.com", "HumanBrainProject",
                schemamodel, "master", version2use, ""])
        
        # open definitions.json from GitHub repository
        temp_html = urllib.request.urlopen(
                schemaorigin + "definitions.json").read()
        definitions = json.loads(temp_html)
        
        # get extract schema names from definitions
        schema_names = list(definitions['definitions'].keys())
        self.schema_names = schema_names

        # dynamically create class attributes for all available schemas
        self.schemas = collections.namedtuple('schemas', schema_names)
        
        # dynamically define schemas as subclasses
        method_desc = ""
        for sn in schema_names:
            # use definitions to download schema from GitHub repository
            temp_html = urllib.request.urlopen(
                    definitions['definitions'][sn]["$ref"]).read()
            jschema = json.loads(temp_html)
         
            self._orig_jschema[sn] = copy.deepcopy(jschema)
            
            jschema['properties'] = dict(
                    (k.replace('@', 'at_'), v) if '@' in k else (k, v) 
                    for k, v in jschema['properties'].items())
            jschema['required'] = list(
                    i.replace('@', 'at_') if '@' in i else i 
                    for i in jschema['required'])   
            
            # transpose schema to schema subclasses
            setattr(self.schemas, sn, self.__digest_jschema(jschema, name=sn))
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
            jschema_prop = list(jschema['properties'].keys())
            method_desc += "".join(["\n    ", sn, "(",
                    ", ".join(sorted(jschema_prop)), ")"])
        
        # add schema methods summary to class docstring
        self.__doc__ = self.__doc__ + method_desc

    def __digest_jschema(self, schema, name=None):
        """
        Generate a model class based on the provided JSON Schema
        :param schema: dict representing valid JSON schema
        :param name: A name to give the class, if `name` is not in `schema`
        """
        schema = copy.deepcopy(schema)
        class JSchema(baseJSchema):
            def __init__(self, *args, **kwargs):
                self.__dict__["schema"] = schema
    
                cls = validator_for(self.schema)
                self.__dict__["validator_instance"] = cls(schema)
    
                baseJSchema.__init__(self, *args, **kwargs)
    
        if name is not None:
            JSchema.__name__ = name
        elif "name" in schema:
            JSchema.__name__ = str(schema["name"])
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
        
if __name__ == "__main__":
    test = CompileOpenMINDS('openMINDS', 'v1.0')
    # print all names of the schemas
    for sn in test.schema_names:
        print(sn)
    # creat a dictionary (compliant with json-ld) of a person
    person_jsonld = test.schemas.CORE_PERSON(
            at_id="minds/core/person/v1.0.0/person01.json",
            at_type="https://schema.hbp/minds/Person",
            name="Doe, Jon",
            shortName="Doe, J.")
    # print the content of your person
    print(person_jsonld.items)
    # check what is needed to get args for subject
    help(test.schemas.EXPERIMENT_SUBJECT)
