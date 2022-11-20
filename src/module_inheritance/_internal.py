import inspect
import os.path
import sys
import os
import importlib
import importlib.abc
import importlib.util
import importlib.machinery
import ast


class _ParentModuleDiscovery(object):

    def __getattr__(self, item):
        frame = sys._getframe().f_back
        module_name = frame.f_globals.get("__name__")
        if module_name:
            registered_module = InheritanceManager.registered_modules.get(module_name)
            if registered_module:
                member = self._get_member(registered_module, frame, item)
                if member:
                    return member

        raise AttributeError()

    def _get_member(self, registered_module, frame, item):
        return None


class ParentModuleDiscovery(_ParentModuleDiscovery):

    def _get_member(self, registered_module, frame, item):
        return registered_module.resolve_member_hierarchy(frame.f_globals.get("__file__"), item)


class BaseModuleDiscovery(_ParentModuleDiscovery):

    def _get_member(self, registered_module, frame, item):
        return registered_module.resolve_member_from_base(item)


class RegisteredModule(object):

    _default_module_members = ["__builtins__", "__doc__", "__file__", "__spec__", "__cached__", "__name__", "__package__", "__path__", "__loader__"]

    class SubModule(object):

        def __init__(self, module, parent):
            self._parent = parent
            self._module = module
            self._dict = {}

        def set_unmodified_dict(self, unmodified_dict):
            self._dict = dict(unmodified_dict)

        @property
        def parent(self):
            return self._parent

        @property
        def module(self):
            return self._module

        @property
        def filename(self):
            return self._module.__file__

        def get_member(self, member):
            return self._dict.get(member)

    def __init__(self, name, path):
        self._name = name
        self._path = None
        if path:
            self._path = path
        self._module = None
        self._main_loader = None
        self._override_modules = {}
        self._main_import_names = []

    def _reset(self):
        self._module = None
        self._override_modules = {}
        self._main_import_names = []

    @property
    def module(self):
        if self._module:
            return self._module.module
        return None

    def resolve_member_hierarchy(self, filename, member):
        current_module = self._override_modules.get(filename)
        if not current_module:
            return None

        current_parent = current_module.parent
        while current_parent:
            overriden_member = current_parent.get_member(member)
            if overriden_member:
                return overriden_member
            current_parent = current_parent.parent

        return None

    def resolve_member_from_base(self, member):
        return self._module.get_member(member)

    def import_module(self):
        self._reset()
        # main package/module
        spec_finder = importlib.machinery.PathFinder()
        main_spec = spec_finder.find_spec(self._name, self._path)
        main_module = importlib.util.module_from_spec(main_spec)
        sys.modules[self._name] = main_module
        self._module = self.SubModule(main_module, None)
        self._main_loader = main_spec.loader
        setattr(main_module, "__hierarchy_module__", self)

    def exec_module(self):
        self._main_loader.exec_module(self._module.module)
        self._module.set_unmodified_dict(self._module.module.__dict__)
        self._main_import_names = self._load_import_nodes(self._main_loader)
        module_path_parts = self._name.split(".")
        if not self._main_loader.is_package(self._name):
            module_path_parts = module_path_parts[:-1]

        current_parent = self._module
        self._override_modules[current_parent.filename] = current_parent
        for path in InheritanceManager.registered_paths:
            module_path = os.path.join(path, *module_path_parts, os.path.basename(self._main_loader.path))

            override_spec = importlib.util.spec_from_file_location(self._name, module_path)
            override_module = importlib.util.module_from_spec(override_spec)
            sub_module = self.SubModule(override_module, current_parent)
            self._override_modules[sub_module.filename] = sub_module
            try:
                override_spec.loader.exec_module(override_module)
            except FileNotFoundError:
                del self._override_modules[sub_module.filename]
                continue

            sub_module.set_unmodified_dict(override_module.__dict__)
            self._override_main_with(override_module)

            current_parent = sub_module

    def _load_import_nodes(self, loader):
        parsed_ast = ast.parse(loader.get_source(self._name))
        import_nodes = []
        for node in parsed_ast.body:
            node_type = type(node)
            if node_type == ast.Import or node_type == ast.ImportFrom:
                for name_node in node.names:
                    import_nodes.append(name_node.asname) if name_node.asname else import_nodes.append(name_node.name)

    def _override_main_with(self, override_module):

        for member_name, member_value in override_module.__dict__.items():

            # ignore any members not in root dictionary
            if member_name not in self._module.module.__dict__ or member_name in self._default_module_members:
                continue

            if inspect.isbuiltin(member_value) or inspect.ismethod(member_value) or inspect.ismodule(member_value):
                continue

            if inspect.isclass(member_value) or inspect.isfunction(member_value):
                if member_value.__module__ != self._module.module.__name__ or self._module.module.__dict__[member_name].__module__ != self._module.module.__name__:
                    continue

            # override the member from the root module with the content from override module
            self._module.module.__dict__[member_name] = member_value


class InheritanceManager(object):

    registered_paths = []
    known_modules = set()
    registered_modules = {}

    @classmethod
    def register_path(cls, path: str):
        if path not in cls.registered_paths and os.path.isdir(path):
            cls.registered_paths.append(path)
        else:
            return

        # discover root modules/packages
        for entry_name in os.listdir(path):
            cls.known_modules.add(os.path.splitext(entry_name)[0])

    class Loader(importlib.abc.Loader):

        def __init__(self, path = None):
            super(InheritanceManager.Loader, self).__init__()
            self._path = path

        def create_module(self, spec):
            if spec.name in sys.modules:
                pass

            if spec.name in InheritanceManager.registered_modules:
                registered_module = InheritanceManager.registered_modules[spec.name]
            else:
                registered_module = RegisteredModule(spec.name, self._path)

            InheritanceManager.registered_modules[spec.name] = registered_module
            registered_module.import_module()
            return registered_module.module
            # spec = importlib.util.spec_from_file_location("module.name", "/path/to/file.py")
            # foo = importlib.util.module_from_spec(spec)
            # sys.modules["module.name"] = foo
            # spec.loader.exec_module(foo)

        def exec_module(self, module):
            hierarchy_module = getattr(module, "__hierarchy_module__", None)
            if hierarchy_module:
                hierarchy_module.exec_module()
            else:
                module.__loader__.exec_module(module)

    class InheritanceMetaImporter(object):

        def find_spec(self, fullname, path, target=None):
            loader = None

            for module in InheritanceManager.known_modules:
                if fullname.startswith(module + "."):
                    if path is None:
                        return None
                    loader = InheritanceManager.Loader(path)
                    break
                elif fullname == module:
                    loader = InheritanceManager.Loader()
                    break

            if loader:
                return importlib.util.spec_from_loader(fullname, loader)
            return None

    @classmethod
    def register_meta_importer(cls):
        sys.meta_path.insert(2, cls.InheritanceMetaImporter())


InheritanceManager.register_meta_importer()

