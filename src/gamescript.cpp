#include <boost/python.hpp>
#include <src/scriptmanager.h>
#include <src/gamescene.h>
#include <src/util.h>
#include <src/CBuilding.h>
#include <src/interaction.h>
#include <src/stats.h>
#include <string>
BOOST_PYTHON_MODULE(_game)
{
    boost::python::class_<CBuilding, boost::noncopyable>("CBuilding", boost::python::no_init)
    PY_PROPERTY_ACCESSOR(CBuilding);
    boost::python::class_<Damage>("Damage")
        .add_property("fire", &Damage::getFire, &Damage::setFire)
        .add_property("frost", &Damage::getFrost, &Damage::setFrost)
        .add_property("thunder", &Damage::getThunder, &Damage::setThunder)
        .add_property("normal", &Damage::getNormal, &Damage::setNormal)
        .add_property("shadow", &Damage::getShadow, &Damage::setShadow);
    boost::python::class_<Interaction, boost::noncopyable>("Interaction", boost::python::no_init);
    boost::python::class_<Coords>("Coords", boost::python::init<int, int, int>())
        .def_readwrite("x", &Coords::x)
        .def_readwrite("y", &Coords::y)
        .def_readwrite("z", &Coords::z);
}
