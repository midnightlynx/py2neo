#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2011-2016, Nigel Small
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

""" OGM Tests

Fundamental entities are:
- GraphObject (node)
- RelationshipSet

# Load, update and push an object
keanu = Person.load("Keanu Reeves")
keanu.name = "Keanu John Reeves"
graph.push(keanu)

# Load, update and push an object and its relationships
keanu = Person.load("Keanu Reeves")
keanu.name = "Keanu John Reeves"
keanu.acted_in.add(Movie("Bill & Ted 3"), roles=['Ted "Theodore" Logan'])
keanu.acted_in.remove(Movie("The Matrix Reloaded"))
graph.push(keanu | keanu.acted_in)

nigel = Person("Nigel Small")
graph.push(nigel)

graph.delete(nigel)
"""


from os.path import join as path_join, dirname
from unittest import TestCase

from py2neo import order, size, remote
from py2neo.ogm import GraphObject, Label, Property, Related
from test.util import GraphTestCase


class MovieGraphObject(GraphObject):
    pass


class Person(MovieGraphObject):
    __primarykey__ = "name"

    name = Property()
    year_of_birth = Property(key="born")

    acted_in = Related("Film")
    directed = Related("test.test_ogm.Film")
    produced = Related("test.test_ogm.Film")


class Film(MovieGraphObject):
    __primarylabel__ = "Movie"
    __primarykey__ = "title"

    awesome = Label()
    musical = Label()
    science_fiction = Label(name="SciFi")

    title = Property()
    tag_line = Property(key="tagline")
    year_of_release = Property(key="released")

    def __init__(self, title):
        self.title = title


class MacGuffin(MovieGraphObject):
    pass


class MovieGraphTestCase(GraphTestCase):

    def setUp(self):
        MovieGraphObject.__graph__ = self.graph
        self.graph.delete_all()
        self.graph.schema.create_uniqueness_constraint("Person", "name")
        with open(path_join(dirname(__file__), "..", "resources", "movies.cypher")) as f:
            cypher = f.read()
        self.graph.run(cypher)

    def tearDown(self):
        self.graph.schema.drop_uniqueness_constraint("Person", "name")
        self.graph.delete_all()


class SubclassTestCase(TestCase):

    def test_class_primary_label_defaults_to_class_name(self):
        assert MacGuffin.__primarylabel__ == "MacGuffin"

    def test_class_primary_label_can_be_overridden(self):
        assert Film.__primarylabel__ == "Movie"

    def test_class_primary_key_defaults_to_id(self):
        assert MacGuffin.__primarykey__ == "__id__"

    def test_class_primary_key_can_be_overridden(self):
        assert Film.__primarykey__ == "title"


class InstanceTestCase(TestCase):

    def setUp(self):
        self.macguffin = MacGuffin()
        self.film = Film("Die Hard")

    def test_instance_primary_label_defaults_to_class_name(self):
        assert self.macguffin.__primarylabel__ == "MacGuffin"

    def test_instance_primary_label_can_be_overridden(self):
        assert self.film.__primarylabel__ == "Movie"

    def test_instance_primary_key_defaults_to_id(self):
        assert self.macguffin.__primarykey__ == "__id__"

    def test_instance_primary_key_can_be_overridden(self):
        assert self.film.__primarykey__ == "title"


class InstanceSubgraphTestCase(TestCase):

    def setUp(self):
        self.film = Film("Die Hard")
        self.film_node = self.film.__subgraph__

    def test_instance_subgraph_is_node_like(self):
        assert order(self.film_node) == 1
        assert size(self.film_node) == 0

    def test_instance_subgraph_inherits_primary_label(self):
        assert self.film_node.__primarylabel__ == "Movie"

    def test_instance_subgraph_inherits_primary_key(self):
        assert self.film_node.__primarykey__ == "title"


class InstanceLabelTestCase(TestCase):

    def setUp(self):
        self.film = Film("Die Hard")
        self.film.awesome = True
        self.film.science_fiction = True
        self.film_node = self.film.__subgraph__

    def test_instance_label_name_defaults_to_attribute_name_variant(self):
        assert self.film_node.has_label("Awesome")

    def test_instance_label_name_can_be_overridden(self):
        assert self.film_node.has_label("SciFi")
        assert not self.film_node.has_label("ScienceFiction")

    def test_instance_label_defaults_to_absent(self):
        assert not self.film_node.has_label("Musical")


class InstancePropertyTestCase(TestCase):

    def setUp(self):
        self.film = Film("Die Hard")
        self.film.year_of_release = 1988
        self.film_node = self.film.__subgraph__

    def test_instance_property_key_defaults_to_attribute_name(self):
        assert "title" in self.film_node

    def test_instance_property_key_can_be_overridden(self):
        assert "released" in self.film_node
        assert "year_of_release" not in self.film_node


class InstanceRelatedObjectTestCase(MovieGraphTestCase):

    def test_related_objects_are_automatically_loaded(self):
        keanu = Person.load_one("Keanu Reeves")
        film_titles = set(film.title for film in list(keanu.acted_in))
        assert film_titles == {"The Devil's Advocate", 'The Matrix Reloaded', "Something's Gotta Give",
                               'The Matrix', 'The Replacements', 'The Matrix Revolutions', 'Johnny Mnemonic'}

    def test_related_objects_subgraph_is_a_set_of_outgoing_relationships(self):
        keanu = Person.load_one("Keanu Reeves")
        subgraph = keanu.acted_in.__subgraph__
        assert order(subgraph) == 8
        assert size(subgraph) == 7
        keanu_node = keanu.__subgraph__
        for relationship in subgraph.relationships():
            assert relationship.start_node() == keanu_node
            assert relationship.type() == "ACTED_IN"
            assert relationship.end_node().has_label("Movie")

    # def test_can_add_and_push_related_object(self):
    #     keanu = Person.load_one("Keanu Reeves")
    #     bill_and_ted = Film("Bill & Ted's Excellent Adventure")
    #     keanu.acted_in.add(bill_and_ted)
    #     self.graph.push(keanu.acted_in)
    #     remote_node = remote(keanu.__subgraph__)
    #     film_titles = set(title for title, in self.graph.run("MATCH (a:Person)-[:ACTED_IN]->(b) "
    #                                                          "WHERE id(a) = {x} "
    #                                                          "RETURN b.title", x=remote_node._id))
    #     assert film_titles == {"The Devil's Advocate", 'The Matrix Reloaded', "Something's Gotta Give",
    #                            'The Matrix', 'The Replacements', 'The Matrix Revolutions', 'Johnny Mnemonic',
    #                            "Bill & Ted's Excellent Adventure"}
    #
    # def test_can_add_and_push_related_object_with_properties(self):
    #     keanu = Person.load_one("Keanu Reeves")
    #     bill_and_ted = Film("Bill & Ted's Excellent Adventure")
    #     keanu.acted_in.add(bill_and_ted, roles=['Ted "Theodore" Logan'])
    #     self.graph.push(keanu.acted_in)
    #     remote_node = remote(keanu.__subgraph__)
    #     films = {title: roles for title, roles in self.graph.run("MATCH (a:Person)-[ab:ACTED_IN]->(b) "
    #                                                              "WHERE id(a) = {x} "
    #                                                              "RETURN b.title, ab.roles", x=remote_node._id)}
    #     bill_and_ted_roles = films["Bill & Ted's Excellent Adventure"]
    #     assert bill_and_ted_roles == ['Ted "Theodore" Logan']

    # TODO: remove related object
    # TODO: remove related object that has other relationships
    # TODO: add property to existing relationship
    # TODO: remove property from existing relationship
    # TODO: change property on existing relationship
    # TODO: push node and relationship set together


class LoadOneTestCase(MovieGraphTestCase):

    def test_can_load_one_object(self):
        keanu = Person.load_one("Keanu Reeves")
        assert keanu.name == "Keanu Reeves"
        assert keanu.year_of_birth == 1964

    def test_cannot_load_one_that_does_not_exist(self):
        keanu = Person.load_one("Keanu Jones")
        assert keanu is None


class LoadTestCase(MovieGraphTestCase):

    def test_can_load_multiple_objects(self):
        keanu, hugo = list(Person.load(["Keanu Reeves", "Hugo Weaving"]))
        assert keanu.name == "Keanu Reeves"
        assert keanu.year_of_birth == 1964
        assert hugo.name == "Hugo Weaving"
        assert hugo.year_of_birth == 1960


class PushTestCase(MovieGraphTestCase):

    def test_can_load_and_push(self):
        keanu = Person.load_one("Keanu Reeves")
        keanu.name = "Keanu Charles Reeves"
        assert keanu.__subgraph__["name"] == "Keanu Charles Reeves"
        self.graph.push(keanu)
        remote_node = remote(keanu.__subgraph__)
        pushed_name = self.graph.evaluate("MATCH (a:Person) WHERE id(a) = {x} "
                                          "RETURN a.name", x=remote_node._id)
        assert pushed_name == "Keanu Charles Reeves"


class PullTestCase(MovieGraphTestCase):

    def test_can_load_and_pull(self):
        keanu = Person.load_one("Keanu Reeves")
        assert keanu.name == "Keanu Reeves"
        remote_node = remote(keanu.__subgraph__)
        self.graph.run("MATCH (a:Person) WHERE id(a) = {x} SET a.name = {y}",
                       x=remote_node._id, y="Keanu Charles Reeves")
        self.graph.pull(keanu)
        assert keanu.name == "Keanu Charles Reeves"