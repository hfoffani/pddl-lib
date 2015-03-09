using System;
#if NUNIT
using TestClass = NUnit.Framework.TestFixtureAttribute;
using TestMethod = NUnit.Framework.TestAttribute;
using TestCleanup = NUnit.Framework.TearDownAttribute;
using TestInitialize = NUnit.Framework.SetUpAttribute;
using ClassCleanup = NUnit.Framework.TestFixtureTearDownAttribute;
using ClassInitialize = NUnit.Framework.TestFixtureSetUpAttribute;
using NUnit.Framework;
#else
using Microsoft.VisualStudio.TestTools.UnitTesting;
#endif

using PDDLNET;

namespace PDDLNETTEST {

[TestClass]
public class TS_PDDLNET {

    [TestMethod]
    public void UseCase_01() {
        var d1 = "../examples-pddl/domain-01.pddl";
        var p1 = "../examples-pddl/problem-01.pddl";
        var pd = new PDDLNET.DomainProblem(d1, p1);
    }


    [TestInitialize()]
    public void BeforeTest() {
        System.Threading.SynchronizationContext.SetSynchronizationContext(
            new System.Threading.SynchronizationContext());
     }

}
}
