"""
PyOriginXML and OriginXML class.
This script is a collection of tools to provide easy python access to OriginLab
tree objects. PyOrigin may be used one day, but for now Tree.Save and Tree.Load
are standard OriginC features which conversion between origin tree objects and
XML strings. These python scripts can access vaues and delicately change them
while preserving the strict structure Origin needs to re-load it into the same
tree object. There are numerous modules that do XML object manipulation, but
this one is made with PyOrigin in mind and is extremely careful to preserve
all formatting.

    * XML=OriginXML(thing) initiates the xml object
        * if thing is an XML string, it will parse it
        * if thing is a path to a file on the disk, it will pull its contents
    * XML.keys() lists keys
        * keys are the names of all parent objects for a value
        * with "<a><b><c>d</c></b></a>" the key "a.b.c" is value "d"
    * XML.value(key) returns the value of key
    * XML.set("a.b.c") sets the value of key to "this"
        * you can't create notes by assigning values to nonexistant keys
        * this is intentional, to preserve the precise data structure
    * return XML string (or save to file) with XML.toString()

http://www.originlab.com/doc/OriginC/ref/Tree-Save
http://www.originlab.com/doc/OriginC/ref/Tree-Load
"""

import os

#TODO: what happens if < makes it in a string?

class OriginXML():
    def __init__(self,xml):
        """Initiate with a string or XML file path."""
        self.PREFIX="?xml.OriginStorage." # ignore what every key will always have
        if "<" in xml:
            print("initializing with XML from string")
            self.path=None
        else:
            self.path=os.path.abspath(xml)
            print("loading XML from:",self.path)
            if os.path.exists(xml):
                with open(xml) as f:
                    xml=f.read()
            else:
                print("ERROR! path not found:",xml)
                return
        print("xml input string is %d bytes"%len(xml))
        if not "OriginStorage" in xml:
            print("WARNING: this doesn't look like an origin tree!")
            self.PREFIX=""
        xml=xml.replace("<","\n<").split("\n")
        for pos,line in enumerate(xml):
            if not line.startswith("<") and len(line):
                #TODO: this line has a linebreak in it! What do we do?
                pass
        self.values={} #values[key]=[line,value]
        levels=[]
        for pos,line in enumerate(xml):
            if not ("<" in line and ">" in line):
                continue           
            line=line.replace(">"," >",1)
            name=line.split(" ",1)[0][1:].replace(">","")
            val=line.split(">")[1]
            if not len(val):
                val=None
            if line.startswith("</"):
                levels.pop()
            elif line.startswith("<"):
                levels.append(name)
                key=".".join(levels)
                if ("/>") in line:
                    levels.pop()
            else:
                print("I DONT KNOW WHAT TO DO WITH THIS LINE")
                print(pos,line,"=",val)
            if val is None:
                continue
            key=key.replace(self.PREFIX,'')
            #print(">>",pos,key,val)
            self.values[key]=[pos,val]
        self.xml=xml
        print("xml now has %d lines and %d keys"%(len(self.xml),len(self.values.keys())))
        
    def keys(self):
        """return a list of all available keys from the XML"""
        return sorted(list(self.values.keys()))
        
    def value(self,key):
        """given a key, return its value from the XML"""
        if not key in self.values.keys():
            print("key [%s] is not in the XML keys")
            return None
        pos,val=self.values[key]
        return val
        
    def set(self,key,newVal):
        """given a key, set its value"""
        if not key in self.values.keys():
            print("key [%s] is not in the XML keys")
            return
        newVal=str(newVal) #everything in an xml string is a string
        pos,oldVal=self.values[key]
        self.xml[pos]=self.xml[pos].replace(oldVal,newVal)
        self.values[key]=pos,newVal

    def toString(self,saveAs=False):
        """return or save XML in the format Origin wants."""
        xml="".join(self.xml)
        print("xml output string is %d bytes"%len(xml))
        if saveAs:
            with open(saveAs,'w') as f:
                f.write(xml)
            print("wrote",saveAs)
        return xml

if __name__=="__main__":   
    ### DEMO USAGE
    #XML=OriginXML('<html><head><style>css</style></head><body>lolz</body></html>')
    XML=OriginXML('data.xml')
    print("KEYS:",XML.keys()) # show available keys
    print("BEFORE:",XML.value("html.body")) # show value for a key
    XML.set("html.body","something more professional") # set a value by its key
    print("AFTER:",XML.value("html.body")) # show value for a key
    XML.toString("output.xml")

    print("DONE")