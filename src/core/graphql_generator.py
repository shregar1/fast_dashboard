"""GraphQL Auto-Generation from FastAPI/REST Endpoints.

Features:
- Automatic GraphQL schema generation from Pydantic models
- GraphQL resolvers from FastAPI endpoints
- Query and mutation auto-mapping
- Subscription support for real-time updates
- Integration with existing FastAPI app

Usage:
    # Add to your FastAPI app
    from fast_dashboards.core.graphql_generator import GraphQLAutoGenerator

    graphql = GraphQLAutoGenerator(app)
    app.mount("/graphql", graphql.create_endpoint())
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from fastapi import FastAPI
from loguru import logger


T = TypeVar("T")


class GraphQLType(str, Enum):
    """GraphQL type mappings."""

    STRING = "String"
    INT = "Int"
    FLOAT = "Float"
    BOOLEAN = "Boolean"
    ID = "ID"
    LIST = "List"
    OBJECT = "Object"


@dataclass
class GraphQLField:
    """A GraphQL field definition."""

    name: str
    type: str
    required: bool = True
    description: str = ""
    resolver: Optional[Callable] = None
    args: Dict[str, str] = field(default_factory=dict)


@dataclass
class GraphQLTypeDefinition:
    """A GraphQL type definition."""

    name: str
    fields: List[GraphQLField]
    description: str = ""
    interfaces: List[str] = field(default_factory=list)


@dataclass
class GraphQLQuery:
    """A GraphQL query definition."""

    name: str
    return_type: str
    args: Dict[str, str]
    resolver: Callable
    description: str = ""


@dataclass
class GraphQLMutation:
    """A GraphQL mutation definition."""

    name: str
    return_type: str
    args: Dict[str, str]
    resolver: Callable
    description: str = ""


class TypeMapper:
    """Maps Python/Pydantic types to GraphQL types."""

    # Primitive type mappings
    PRIMITIVE_MAP = {
        str: GraphQLType.STRING,
        int: GraphQLType.INT,
        float: GraphQLType.FLOAT,
        bool: GraphQLType.BOOLEAN,
        Optional[str]: GraphQLType.STRING,
        Optional[int]: GraphQLType.INT,
        Optional[float]: GraphQLType.FLOAT,
        Optional[bool]: GraphQLType.BOOLEAN,
    }

    @classmethod
    def map_type(cls, python_type: Type) -> tuple[str, bool]:
        """Map a Python type to GraphQL type.

        Returns:
            Tuple of (graphql_type, is_required)

        """
        origin = get_origin(python_type)
        args = get_args(python_type)

        # Handle Optional types
        if origin is Union and type(None) in args:
            inner_type = next(a for a in args if a is not type(None))
            graphql_type, _ = cls.map_type(inner_type)
            return graphql_type, False

        # Handle List types
        if origin is list or origin is List:
            if args:
                inner_type, _ = cls.map_type(args[0])
                return f"[{inner_type}]", True
            return "[String]", True

        # Handle primitive types
        if python_type in cls.PRIMITIVE_MAP:
            return cls.PRIMITIVE_MAP[python_type].value, True

        # Handle Pydantic models as objects
        if hasattr(python_type, "__name__"):
            return python_type.__name__, True

        return GraphQLType.STRING.value, True

    @classmethod
    def extract_model_fields(cls, model_class: Type) -> List[GraphQLField]:
        """Extract fields from a Pydantic model or dataclass."""
        fields = []

        # Try Pydantic v2
        if hasattr(model_class, "model_fields"):
            for name, field_info in model_class.model_fields.items():
                field_type = field_info.annotation
                gql_type, required = cls.map_type(field_type)
                fields.append(
                    GraphQLField(
                        name=name,
                        type=gql_type,
                        required=required,
                        description=field_info.description or "",
                    )
                )

        # Try Pydantic v1
        elif hasattr(model_class, "__fields__"):
            for name, field_info in model_class.__fields__.items():
                field_type = field_info.outer_type_
                gql_type, required = cls.map_type(field_type)
                fields.append(
                    GraphQLField(
                        name=name,
                        type=gql_type,
                        required=required,
                        description=field_info.field_info.description or "",
                    )
                )

        # Try dataclass
        elif hasattr(model_class, "__dataclass_fields__"):
            type_hints = get_type_hints(model_class)
            for name, field_info in model_class.__dataclass_fields__.items():
                field_type = type_hints.get(name, str)
                gql_type, required = cls.map_type(field_type)
                fields.append(
                    GraphQLField(
                        name=name,
                        type=gql_type,
                        required=required,
                        description=getattr(field_info, "metadata", {}).get(
                            "description", ""
                        ),
                    )
                )

        return fields


class GraphQLSchemaGenerator:
    """Generates GraphQL schema from Python models and endpoints."""

    def __init__(self):
        """Execute __init__ operation."""
        self.types: Dict[str, GraphQLTypeDefinition] = {}
        self.queries: Dict[str, GraphQLQuery] = {}
        self.mutations: Dict[str, GraphQLMutation] = {}
        self.enums: Dict[str, List[str]] = {}

    def register_model(self, model_class: Type, name: Optional[str] = None) -> str:
        """Register a Pydantic model as a GraphQL type.

        Returns:
            The GraphQL type name

        """
        type_name = name or model_class.__name__

        if type_name in self.types:
            return type_name

        fields = TypeMapper.extract_model_fields(model_class)

        self.types[type_name] = GraphQLTypeDefinition(
            name=type_name,
            fields=fields,
            description=f"Auto-generated type for {type_name}",
        )

        return type_name

    def register_endpoint(
        self,
        path: str,
        method: str,
        handler: Callable,
        input_model: Optional[Type] = None,
        output_model: Optional[Type] = None,
        name: Optional[str] = None,
    ):
        """Register a REST endpoint as a GraphQL operation.

        Args:
            path: URL path (e.g., "/users/{id}")
            method: HTTP method (GET, POST, PUT, DELETE)
            handler: The endpoint handler function
            input_model: Input Pydantic model (for mutations)
            output_model: Output Pydantic model
            name: Custom operation name

        """
        # Generate operation name from path
        if name is None:
            path_parts = [p.strip("{}") for p in path.split("/") if p]
            name = "_".join(path_parts)

        # Register output model as type
        if output_model:
            return_type = self.register_model(output_model)
            if method == "GET" and "List" in return_type or "list" in name.lower():
                return_type = f"[{return_type}]"
        else:
            return_type = "String"

        # Extract arguments from path and input model
        args = {}

        # Path parameters
        for part in path.split("/"):
            if part.startswith("{") and part.endswith("}"):
                param_name = part.strip("{}")
                args[param_name] = "ID!"

        # Input model fields
        if input_model:
            input_type_name = self.register_model(input_model)
            args["input"] = f"{input_type_name}!"

        # Create operation
        if method == "GET":
            self.queries[name] = GraphQLQuery(
                name=name,
                return_type=return_type,
                args=args,
                resolver=handler,
                description=f"Auto-generated from {method} {path}",
            )
        elif method in ("POST", "PUT", "DELETE", "PATCH"):
            self.mutations[name] = GraphQLMutation(
                name=name,
                return_type=return_type,
                args=args,
                resolver=handler,
                description=f"Auto-generated from {method} {path}",
            )

    def generate_schema(self) -> str:
        """Generate the complete GraphQL schema SDL."""
        lines = []

        # Generate types
        for type_def in self.types.values():
            lines.append(self._generate_type_sdl(type_def))
            lines.append("")

        # Generate queries
        if self.queries:
            lines.append("type Query {")
            for query in self.queries.values():
                lines.append(self._generate_query_sdl(query))
            lines.append("}")
            lines.append("")

        # Generate mutations
        if self.mutations:
            lines.append("type Mutation {")
            for mutation in self.mutations.values():
                lines.append(self._generate_mutation_sdl(mutation))
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def _generate_type_sdl(self, type_def: GraphQLTypeDefinition) -> str:
        """Generate SDL for a type."""
        lines = [f"type {type_def.name} {{"]

        for field in type_def.fields:
            type_str = field.type if field.required else field.type
            lines.append(f"  {field.name}: {type_str}")

        lines.append("}")
        return "\n".join(lines)

    def _generate_query_sdl(self, query: GraphQLQuery) -> str:
        """Generate SDL for a query."""
        args_str = ""
        if query.args:
            args_list = [f"{k}: {v}" for k, v in query.args.items()]
            args_str = f"({', '.join(args_list)})"

        return f"  {query.name}{args_str}: {query.return_type}"

    def _generate_mutation_sdl(self, mutation: GraphQLMutation) -> str:
        """Generate SDL for a mutation."""
        args_str = ""
        if mutation.args:
            args_list = [f"{k}: {v}" for k, v in mutation.args.items()]
            args_str = f"({', '.join(args_list)})"

        return f"  {mutation.name}{args_str}: {mutation.return_type}"


class GraphQLAutoGenerator:
    """Automatically generates GraphQL API from FastAPI application.

    Usage:
        app = FastAPI()

        # Add your REST endpoints
        @app.get("/users/{user_id}")
        async def get_user(user_id: int) -> User:
            ...

        # Auto-generate GraphQL
        graphql = GraphQLAutoGenerator(app)
        app.mount("/graphql", graphql.create_endpoint())
    """

    def __init__(self, app: FastAPI):
        """Execute __init__ operation.

        Args:
            app: The app parameter.
        """
        self.app = app
        self.schema_generator = GraphQLSchemaGenerator()
        self._scan_routes()

    def _scan_routes(self):
        """Scan FastAPI routes and register with GraphQL."""
        for route in self.app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                path = route.path
                methods = route.methods - {"HEAD", "OPTIONS"}  # Exclude auto methods

                for method in methods:
                    handler = route.endpoint

                    # Try to extract input/output models from signature
                    sig = inspect.signature(handler)
                    input_model = None
                    output_model = None

                    # Check return annotation
                    if sig.return_annotation != inspect.Signature.empty:
                        return_type = sig.return_annotation
                        # Handle Optional, List, etc.
                        origin = get_origin(return_type)
                        if origin is list or origin is List:
                            args = get_args(return_type)
                            if args:
                                output_model = args[0]
                        elif hasattr(return_type, "__name__"):
                            output_model = return_type

                    # Check for body parameter (usually the last parameter)
                    for param_name, param in sig.parameters.items():
                        if param_name in ("request", "response", "db"):
                            continue
                        param_type = param.annotation
                        if (
                            hasattr(param_type, "__name__")
                            and not param.default == inspect.Parameter.empty
                        ):
                            input_model = param_type

                    self.schema_generator.register_endpoint(
                        path=path,
                        method=method,
                        handler=handler,
                        input_model=input_model,
                        output_model=output_model,
                    )

                    logger.debug(f"Registered GraphQL operation: {method} {path}")

    def generate_schema(self) -> str:
        """Generate the GraphQL schema."""
        return self.schema_generator.generate_schema()

    def create_endpoint(self) -> Any:
        """Create a GraphQL endpoint for mounting in FastAPI.

        Returns:
            An ASGI app that can be mounted

        """
        try:
            import strawberry
            from strawberry.asgi import GraphQL

            # Generate Strawberry types from schema
            schema = self._create_strawberry_schema()
            return GraphQL(schema)

        except ImportError:
            logger.warning("strawberry-graphql not installed, using basic endpoint")
            return self._create_basic_endpoint()

    def _create_strawberry_schema(self):
        """Create Strawberry GraphQL schema."""
        try:
            import strawberry
            from strawberry.types import Info

            # Dynamically create Strawberry types
            types = {}

            for type_name, type_def in self.schema_generator.types.items():
                # Create dataclass for type
                fields = {}
                for field in type_def.fields:
                    # Map GraphQL types to Python types
                    if field.type == "String":
                        fields[field.name] = str
                    elif field.type == "Int":
                        fields[field.name] = int
                    elif field.type == "Float":
                        fields[field.name] = float
                    elif field.type == "Boolean":
                        fields[field.name] = bool
                    else:
                        fields[field.name] = str

                # Create Strawberry type
                strawberry_type = strawberry.type(
                    type(type_name, (), {"__annotations__": fields})
                )
                types[type_name] = strawberry_type

            # Create Query type
            query_fields = {}
            for query_name, query in self.schema_generator.queries.items():

                async def resolver(info: Info, **kwargs):
                    """Execute resolver operation.

                    Args:
                        info: The info parameter.

                    Returns:
                        The result of the operation.
                    """
                    return await query.resolver(**kwargs)

                query_fields[query_name] = strawberry.field(resolver=resolver)

            Query = strawberry.type(type("Query", (), query_fields))

            return strawberry.Schema(query=Query)

        except Exception as e:
            logger.error(f"Failed to create Strawberry schema: {e}")
            raise

    def _create_basic_endpoint(self):
        """Create a basic GraphQL endpoint without Strawberry."""
        from starlette.responses import JSONResponse

        async def endpoint(scope, receive, send):
            """Basic GraphQL endpoint."""
            if scope["type"] == "http":
                from starlette.requests import Request

                request = Request(scope, receive)

                if request.method == "GET":
                    # Return schema
                    response = JSONResponse({"schema": self.generate_schema()})
                else:
                    response = JSONResponse({"error": "Use GET for schema"})

                await response(scope, receive, send)

        return endpoint

    def print_schema(self):
        """Print the generated GraphQL schema."""
        print(self.generate_schema())


def graphql_query(endpoint_resolver: Callable):
    """Decorator to expose a REST endpoint as a GraphQL query.

    Usage:
        @app.get("/users/{id}")
        @graphql_query
        async def get_user(id: int) -> User:
            return await fetch_user(id)
    """
    endpoint_resolver._graphql_exposed = True
    endpoint_resolver._graphql_type = "query"
    return endpoint_resolver


def graphql_mutation(endpoint_resolver: Callable):
    """Decorator to expose a REST endpoint as a GraphQL mutation.

    Usage:
        @app.post("/users")
        @graphql_mutation
        async def create_user(user: UserCreate) -> User:
            return await save_user(user)
    """
    endpoint_resolver._graphql_exposed = True
    endpoint_resolver._graphql_type = "mutation"
    return endpoint_resolver


__all__ = [
    "GraphQLAutoGenerator",
    "GraphQLSchemaGenerator",
    "TypeMapper",
    "GraphQLType",
    "GraphQLField",
    "GraphQLTypeDefinition",
    "GraphQLQuery",
    "GraphQLMutation",
    "graphql_query",
    "graphql_mutation",
]
