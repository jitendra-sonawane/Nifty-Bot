let currentFiber = null;
let workInProgressFiber = null;
let hookIndex = 0;
let effectIndex = 0;
let currentHook = null;
let rootDOM = document.getElementById('root');

function createFiber(type) {
    return {
        type,
        memoizedState: null,
        updateQueue: [],
        alternate: null,
        dom: null
    }
}

function useState(initialValue) {
    let oldHook = workInProgressFiber?.alternate?.memoizedState &&
        getHookFromAlternate(hookIndex);

    let hook = {
        state: oldHook ? oldHook.state : initialValue,
        queue: [],
        next: null
    }

    // attached hook to link list
    if (hookIndex === 0)
        workInProgressFiber.memoizedState = hook;
    else currentHook.next = hook;

    currentHook = hook;

    //apply queued updates
    const actions = oldHook ? oldHook.queue : [];
    actions.forEach((update) => {
        hook.state = update(hook.state)
    })

    function setState(action) {
        hook.queue.push(
            typeof action === "function" ? action : () => action
        )
        scheduleUpdate();
    }
    hookIndex++;
    return [hook.state, setState]
}
function getHookFromAlternate(index) {
    let hook = workInProgressFiber?.alternate?.memoizedState;
    for (let i = 0; i < index; i++) hook = hook.next;
    return hook;
}

function useEffect(callback, deps) {
    let oldEffect = workInProgressFiber?.alternate?.updateQueue[effectIndex];
    let hasChanged = true;
    if (oldEffect) {
        hasChanged = deps.some((d, i) => d !== oldEffect.deps[i])
    }
    let effect = {
        callback,
        deps,
        cleanUp: oldEffect ? oldEffect.cleanUp : null,
        hasChanged
    }
    workInProgressFiber.updateQueue.push(effect);
    effectIndex++;

}

function Counter() {
    const [count, setCount] = useState(0);
    const [name, setName] = useState("Jitendra");
    const [lastName, setLastName] = useState("Sonawane");
    useEffect(() => {
        console.log("Effect Runs :count=", count);
        return () => {
            console.log("CleanUp :oldCount=", count);
        }
    }, []);

    // this is where react dom comes into picture
    // it create virtual dom by converting jsx/tsx into objects

    return {
        type: 'div',
        children: [{
            type: 'h2',
            text: "Count:" + count,
        }, {
            type: 'button',
            text: "increment",
            onClick: () => setCount(c => c + 1)
        },
        {
            type: "input",
            value: name,
            onChange: (e) => setName(e.target.value)
        },
        {
            type: "input",
            value: lastName,
            onChange: (e) => setLastName(e.target.value)
        }
        ]
    }
}

function commitDOM(vdom) {

    if (!workInProgressFiber.dom) {
        rootDOM.innerHTML = "";
        const container = document.createElement("div");

        vdom.children.forEach((node) => {
            const el = document.createElement(node.type);
            el.textContent = node.text;

            if (node.type === "button") {
                el.onclick = node.onClick;
            }
            if (node.type === "input") {
                el.value = node.value;
                el.onchange = node.onChange;
            }
            container.appendChild(el);
        })
        rootDOM.appendChild(container);
        workInProgressFiber.dom = container;
    } else {
        const h2 = workInProgressFiber.dom.querySelector("h2");
        h2.textContent = vdom.children[0].text;
    }

}
function runEffects() {
    workInProgressFiber.updateQueue.forEach((effect) => {
        if (effect.hasChanged) {
            if (effect.cleanUp) effect.cleanUp();
            effect.cleanUp = effect.callback();
        }
    })
}
function render() {
    console.log("\n Render phase begins")
    hookIndex = 0;
    effectIndex = 0;
    currentHook = null;

    workInProgressFiber = createFiber(Counter);
    workInProgressFiber.alternate = currentFiber;

    const vdom = Counter();
    console.log("VDOM:", vdom);
    console.log(" Commit phase");
    commitDOM(vdom);
    console.log("Effect Phase")
    runEffects();
    currentFiber = workInProgressFiber;
}

function scheduleUpdate() {
    render();
}
render();