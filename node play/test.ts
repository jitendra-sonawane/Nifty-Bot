console.log('start');
setTimeout(() => {
    console.log('end');
    Promise.resolve().then(() => console.log('promise in setTimeout'));
}, 1000);

Promise.resolve().then(() => { console.log('promise 1'), setTimeout(() => { console.log('setTimeout 2') }, 0) });
// setTimeout(() => { console.log('setTimeout 2') }, 0);