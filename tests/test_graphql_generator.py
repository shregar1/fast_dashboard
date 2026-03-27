"""Tests for GraphQL Auto-Generator."""

import pytest
from dataclasses import dataclass
from typing import List, Optional

from fast_dashboards.core.graphql_generator import (
    TypeMapper,
    GraphQLSchemaGenerator,
    GraphQLType,
    GraphQLField,
    GraphQLTypeDefinition,
    GraphQLQuery,
    GraphQLMutation,
)


class TestTypeMapper:
    """Tests for TypeMapper."""

    def test_map_primitive_types(self):
        """Test mapping primitive Python types to GraphQL."""
        assert TypeMapper.map_type(str) == ("String", True)
        assert TypeMapper.map_type(int) == ("Int", True)
        assert TypeMapper.map_type(float) == ("Float", True)
        assert TypeMapper.map_type(bool) == ("Boolean", True)

    def test_map_optional_types(self):
        """Test mapping Optional types."""
        assert TypeMapper.map_type(Optional[str]) == ("String", False)
        assert TypeMapper.map_type(Optional[int]) == ("Int", False)

    def test_map_list_types(self):
        """Test mapping List types."""
        assert TypeMapper.map_type(List[str]) == ("[String]", True)
        assert TypeMapper.map_type(List[int]) == ("[Int]", True)

    def test_map_custom_types(self):
        """Test mapping custom types."""

        class User:
            """Represents the User class."""

            pass

        gql_type, required = TypeMapper.map_type(User)
        assert gql_type == "User"
        assert required is True

    def test_extract_pydantic_fields(self):
        """Test extracting fields from Pydantic model."""
        try:
            from pydantic import BaseModel, Field

            class User(BaseModel):
                """Represents the User class."""

                name: str
                age: int
                email: Optional[str] = None

            fields = TypeMapper.extract_model_fields(User)

            assert len(fields) >= 2
            field_names = [f.name for f in fields]
            assert "name" in field_names
            assert "age" in field_names

        except ImportError:
            pytest.skip("Pydantic not installed")

    def test_extract_dataclass_fields(self):
        """Test extracting fields from dataclass."""

        @dataclass
        class Product:
            """Represents the Product class."""

            name: str
            price: float
            description: Optional[str] = None

        fields = TypeMapper.extract_model_fields(Product)

        assert len(fields) == 3
        field_names = [f.name for f in fields]
        assert "name" in field_names
        assert "price" in field_names
        assert "description" in field_names


class TestGraphQLSchemaGenerator:
    """Tests for GraphQLSchemaGenerator."""

    @pytest.fixture
    def generator(self):
        """Execute generator operation.

        Returns:
            The result of the operation.
        """
        return GraphQLSchemaGenerator()

    def test_register_model(self, generator):
        """Test registering a model."""

        @dataclass
        class User:
            """Represents the User class."""

            name: str
            email: str

        type_name = generator.register_model(User)

        assert type_name == "User"
        assert "User" in generator.types

    def test_register_endpoint_get(self, generator):
        """Test registering a GET endpoint."""

        async def get_user(user_id: int):
            """Execute get_user operation.

            Args:
                user_id: The user_id parameter.

            Returns:
                The result of the operation.
            """
            pass

        generator.register_endpoint(
            path="/users/{user_id}", method="GET", handler=get_user
        )

        assert len(generator.queries) == 1
        assert "users_user_id" in generator.queries

    def test_register_endpoint_post(self, generator):
        """Test registering a POST endpoint."""

        async def create_user(data: dict):
            """Execute create_user operation.

            Args:
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            pass

        generator.register_endpoint(path="/users", method="POST", handler=create_user)

        assert len(generator.mutations) == 1
        assert "users" in generator.mutations

    def test_generate_schema_with_types(self, generator):
        """Test generating schema with types."""

        @dataclass
        class User:
            """Represents the User class."""

            name: str
            email: str

        generator.register_model(User)

        schema = generator.generate_schema()

        assert "type User" in schema
        assert "name: String" in schema
        assert "email: String" in schema

    def test_generate_schema_with_queries(self, generator):
        """Test generating schema with queries."""

        async def get_user(user_id: int):
            """Execute get_user operation.

            Args:
                user_id: The user_id parameter.

            Returns:
                The result of the operation.
            """
            pass

        generator.register_endpoint(
            path="/users/{user_id}", method="GET", handler=get_user
        )

        schema = generator.generate_schema()

        assert "type Query" in schema
        assert "users_user_id" in schema

    def test_generate_schema_with_mutations(self, generator):
        """Test generating schema with mutations."""

        async def create_user(data: dict):
            """Execute create_user operation.

            Args:
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            pass

        generator.register_endpoint(path="/users", method="POST", handler=create_user)

        schema = generator.generate_schema()

        assert "type Mutation" in schema
        assert "users" in schema


class TestGraphQLTypeDefinition:
    """Tests for GraphQLTypeDefinition."""

    def test_type_creation(self):
        """Test creating a type definition."""
        fields = [
            GraphQLField(name="id", type="ID!", required=True),
            GraphQLField(name="name", type="String!", required=True),
        ]

        type_def = GraphQLTypeDefinition(
            name="User", fields=fields, description="A user"
        )

        assert type_def.name == "User"
        assert len(type_def.fields) == 2


class TestGraphQLOperations:
    """Tests for GraphQL operations."""

    def test_query_creation(self):
        """Test creating a query."""

        async def resolver():
            """Execute resolver operation.

            Returns:
                The result of the operation.
            """
            return "test"

        query = GraphQLQuery(
            name="getUser",
            return_type="User",
            args={"id": "ID!"},
            resolver=resolver,
            description="Get a user",
        )

        assert query.name == "getUser"
        assert query.return_type == "User"
        assert "id" in query.args

    def test_mutation_creation(self):
        """Test creating a mutation."""

        async def resolver():
            """Execute resolver operation.

            Returns:
                The result of the operation.
            """
            return "test"

        mutation = GraphQLMutation(
            name="createUser",
            return_type="User",
            args={"input": "UserInput!"},
            resolver=resolver,
            description="Create a user",
        )

        assert mutation.name == "createUser"
        assert mutation.return_type == "User"


class TestIntegration:
    """Integration tests for GraphQL generator."""

    def test_full_workflow(self):
        """Test complete workflow."""
        generator = GraphQLSchemaGenerator()

        # Define models
        @dataclass
        class User:
            """Represents the User class."""

            id: int
            name: str
            email: str

        @dataclass
        class Post:
            """Represents the Post class."""

            id: int
            title: str
            content: str

        # Register models
        generator.register_model(User)
        generator.register_model(Post)

        # Register endpoints
        async def get_user(user_id: int):
            """Execute get_user operation.

            Args:
                user_id: The user_id parameter.

            Returns:
                The result of the operation.
            """
            pass

        async def list_users():
            """Execute list_users operation.

            Returns:
                The result of the operation.
            """
            pass

        async def create_user(data: dict):
            """Execute create_user operation.

            Args:
                data: The data parameter.

            Returns:
                The result of the operation.
            """
            pass

        generator.register_endpoint("/users/{user_id}", "GET", get_user)
        generator.register_endpoint("/users", "GET", list_users)
        generator.register_endpoint("/users", "POST", create_user)

        # Generate schema
        schema = generator.generate_schema()

        # Verify
        assert "type User" in schema
        assert "type Post" in schema
        assert "type Query" in schema
        assert "type Mutation" in schema
        assert "users" in schema


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
