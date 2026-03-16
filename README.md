# libspec

`libspec` is a library for **Specification Driven Development** in
Python. Similar in spirit to object relation mapping (ORM), libspec
uses an Object Specification Mapping. Instead of generating SQL, this
tool generates specs geared towards code generation with LLMs.

Context is managed by diff'ing specs and using source maps with and
associated agent that can cross reference the specs and generated
code. The developer workflow is incremental and exploratory, less like
gambling and more like delegating.

![the general idea](./docs/workflow1.png)


### Example Spec

Here is a piece of a spec used to declare a small web app for managing
a locker system

```python
from libspec import Requirement, RestMixin, Feature
from .view_types import PublicView, AdminView

class Django(Requirement):
    """Setup a Django environment using 6.0.2, it should use sqlite3 for 
    now. Configure REST_FRAMEWORK and djangorestframework. 
    Create a django app (with $ ... startapp) called `lockers` and 
    wire it up. It should include an example model, view and urls to 
    get started. 
 
    Please ensure that the models are added to admin interface and 
    REST API is exposed.
    """

class Model(RestMixin, Requirement):
    '''ensure this django model is added to the admin interface'''

class LockerBank(Model):
    """Represent a physical bank of lockers. Should include a unique
    name."""

class QrCode(Model):
    """Represent a QR code attached to a locker. Should include a
    unique value, q matching the format in QrCodeRequirement.
    """

class Locker(Model):
    """Represent an individual locker unit. Should be associated with
    a LockerBank and two QrCodes (one inside, one outside). Should
    track occupancy status and the timestamp of the last inside QR
    code scan.  A locker will have a small number that uniquely
    identifies it within a locker bank.  When a locker is created, it
    should automatically create the qr codes associated with it.
    """

class GunicornServer(Requirement):
    '''In the Makefile, create a rule to run the gunicorn server on
    port 8000'''

class DevelopmentServer(Requirement):
    '''In the Makefile, create a rule to run the development server on
    port 8000'''

```

# The Object Model 

Each class declares a specification fragment that is optionally a
Jinja2 template string. More about that later...

## Inheritance

Inherited specification fragments are prepended to the Base class' doc
string.

## Mixins 

Mixins help get around the diamond problem. (TODO: write more about this)

