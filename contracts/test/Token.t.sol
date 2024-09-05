// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/Token.sol";

contract TestTokenTest is Test {
    TestToken public token;
    address public owner;
    address public user;

    function setUp() public {
        owner = address(this);
        user = address(0x1);
        token = new TestToken(owner);
    }

    function testMint() public {
        uint256 amount = 1000 * 10**18;
        token.mint(user, amount);
        assertEq(token.balanceOf(user), amount);
    }

    function testMintOnlyOwner() public {
        vm.prank(user);
        vm.expectRevert();
        token.mint(user, 1000 * 10**18);
    }

    function testTransfer() public {
        uint256 amount = 1000 * 10**18;
        token.transfer(user, amount);
        assertEq(token.balanceOf(user), amount);
        assertEq(token.balanceOf(owner), token.totalSupply() - amount);
    }
}
