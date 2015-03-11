using System;
using System.Collections.Generic;

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

        Assert.IsNotNull(pd);
    }

    [TestMethod]
    public void UseCase_02() {
        var d1 = "../examples-pddl/domain-01.pddl";
        var p1 = "../examples-pddl/problem-01.pddl";
        var pd = new PDDLNET.DomainProblem(d1, p1);

        Assert.IsNotNull(pd);
        Assert.IsNotNull(pd.initialstate);
        foreach (var i in pd.initialstate)
            System.Console.WriteLine("i"+i.ToString());
        Assert.AreEqual(5, pd.initialstate.Count);
        Assert.IsNotNull(pd.goals);
        foreach (var g in pd.goals)
            System.Console.WriteLine("g"+g.ToString());
        Assert.AreEqual(1, pd.goals.Count);

        Assert.IsNotNull(pd.worldobjects);
        Assert.AreEqual(5, pd.worldobjects.Keys.Count);

        Assert.IsNotNull(pd.operators);
        var ops = new List<string>(pd.operators);
        Assert.AreEqual(2, ops.Count);
        Assert.IsTrue(ops.Contains("op1"));
        Assert.IsTrue(ops.Contains("op2"));
    }

    [TestMethod]
    public void UseCase_03() {
        var d1 = "../examples-pddl/domain-01.pddl";
        var p1 = "../examples-pddl/problem-01.pddl";
        var pd = new PDDLNET.DomainProblem(d1, p1);

        Assert.IsNotNull(pd);
        // pd.ground_operator("op1");
    }

    [TestInitialize()]
    public void BeforeTest() {
        System.Threading.SynchronizationContext.SetSynchronizationContext(
            new System.Threading.SynchronizationContext());
     }

}
}
