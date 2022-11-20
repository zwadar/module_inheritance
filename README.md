# Module Inheritance Package

Package to allow overriding python packages in a similar manner as class subclassing works. 
Probably it won't find much use on normal usage scenario. However, it might be very useful in scenarios where one Python code is supposed to run inside multiple different applications embedding Python. 


The override process is automatic and happens on the folder structure. So the main code does not need to be aware of the override process.
Also, it overrides individual members, and not the whole module. So the override files don't need to contain all content from the original module.

## Usage

### Simple

Lets have a module `my_module.py`
```python
def get_python_interpreter():
    return "python.exe"
    
def get_number():
    return 42
```

and then client code
```python
import os
import my_module

os.system(my_module.get_python_interpreter())
print(my_module.get_number())
```

However, some applications while embedding Python, have unique names of their interpreter so the code won't work.
To make the client working across all environments. We first need to create to override module at some path e.g. `my_overrides/my_module.py`
```python
def get_python_interpreter():
    return "custom_intepreter_name.exe"
```

and then register to **root** folder into the system in some application initialisation sequence

```python
import module_inheritance

module_inheritance.register_path("my_overrides")
```

This setup will hijack the import machinery, 
and will cause the `get_python_interpreter` to return new interpreter name, but the `get_number` method will still return `42`.

### Hierarchy

The system is not limited to just one override, and it is possible to register multiple paths.

```python
import module_inheritance

module_inheritance.register_path("my_overrides")
module_inheritance.register_path("my_another_overrides")
module_inheritance.register_path("my_yet_another_overrides")
```

Most recent overrides are then picked.

#### Using `parent` and `base`

With the hierarchy in place, it is also possible to call original overriden methods, the same way `super` is working in the class subclassing.
So for file `my_yet_another_overrides/my_module.py` we can do

```python
import module_inheritance

def get_number():
    return module_inheritance.parent.get_number() * 2
```

`module_inheritance.parent` refers to the closest version of the method in the override hierarchy, on the other hand `module_inheritance.base` refers to the original, unmodified root module.

### Overriding Classes

With the `base` and `parent` member, it is also possible to create override classes by simply subclassing from them and using the same name.
This allows full customisation of the classes in the override code without any need to change the client code.

Let's define new class in `my_module.py`
```python

class MyClass(object):
    
    def __init__(self):
        pass
    
    def do_it(self):
        return 8

```

and then create override in the `my_overrides/my_module.py`

```python
import module_inheritance

class MyClass(module_inheritance.parent.MyClass):
    
    def do_it(self):
        return super() * 2
```