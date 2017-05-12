
/*
 * Copyright 2015 Hernán M. Foffani
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

using System;
using System.Collections.Generic;
using System.Linq;

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
        var d1 = "../../examples-pddl/domain-01.pddl";
        var p1 = "../../examples-pddl/problem-01.pddl";
        var pd = new PDDLNET.DomainProblem(d1, p1);

        Assert.IsNotNull(pd);
    }

    [TestMethod]
    public void UseCase_02() {
        var d1 = "../../examples-pddl/domain-01.pddl";
        var p1 = "../../examples-pddl/problem-01.pddl";
        var pd = new PDDLNET.DomainProblem(d1, p1);

        Assert.IsNotNull(pd);
        Assert.IsNotNull(pd.initialstate);
        Assert.AreEqual(5, pd.initialstate.Count);
        Assert.IsNotNull(pd.goals);
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
        var d1 = "../../examples-pddl/domain-01.pddl";
        var p1 = "../../examples-pddl/problem-01.pddl";
        var pd = new PDDLNET.DomainProblem(d1, p1);

        Assert.IsNotNull(pd);
        var op1_grounds = pd.ground_operator("op1");
        Assert.IsNotNull(op1_grounds);
        var lops = op1_grounds.ToList();
        Assert.AreEqual(125, lops.Count);
    }

    [TestInitialize()]
    public void BeforeTest() {
        System.Threading.SynchronizationContext.SetSynchronizationContext(
            new System.Threading.SynchronizationContext());
     }

public static int Main(string[] args) {
    return new NUnitLite.AutoRun().Execute(args);
}

}

}

