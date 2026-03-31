// 生成的JavaScript代码

function processUserList(users) {
    // 处理用户列表
    users.forEach(user => {
        console.log(`Name: ${user.name}, Email: ${user.email}, Phone: ${user.phone}`);
    });
}

// 示例用法
const users = [
    {name: 'John Doe', email: 'john@example.com', phone: '123-456-7890'},
    {name: 'Jane Smith', email: 'jane@example.com', phone: '987-654-3210'}
];

processUserList(users);
